from django.contrib.sessions.models import Session as DjangoSession
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.sessions import SESSION_STARTED_AT_KEY
from apps.core.models import AuditEvent
from tests.factories import make_user


PASSWORD = "Correct!Password934"


def user_with_password(role=User.Role.STUDENT, **overrides):
    user = make_user(role, **overrides)
    user.set_password(PASSWORD)
    user.save(update_fields=["password", "updated_at"])
    return user


class LoginTests(TestCase):
    def test_class_free_student_can_login_and_reach_dashboard(self):
        student = user_with_password(username="classfree")

        response = self.client.post(
            reverse("account:login"),
            {"username": student.username, "password": PASSWORD},
        )

        self.assertRedirects(response, reverse("account:student_dashboard"))
        dashboard = self.client.get(response.url)
        self.assertContains(dashboard, "Your dashboard")
        self.assertContains(dashboard, "Path setup pending")
        self.assertIn(SESSION_STARTED_AT_KEY, self.client.session)

    def test_successful_login_rotates_existing_session(self):
        student = user_with_password(username="rotate-me")
        session = self.client.session
        session["before_login"] = True
        session.save()
        previous_key = session.session_key

        self.client.post(
            reverse("account:login"),
            {"username": student.username, "password": PASSWORD},
        )

        self.assertNotEqual(previous_key, self.client.session.session_key)
        self.assertFalse(DjangoSession.objects.filter(session_key=previous_key).exists())

    def test_external_next_is_rejected_and_internal_next_is_used(self):
        student = user_with_password(username="safe-next")
        response = self.client.post(
            reverse("account:login") + "?next=https://attacker.example/steal",
            {"username": student.username, "password": PASSWORD},
        )
        self.assertRedirects(response, reverse("account:student_dashboard"))

        self.client.post(reverse("account:logout"))
        response = self.client.post(
            reverse("account:login") + f"?next={reverse('account:my_account')}",
            {"username": student.username, "password": PASSWORD},
        )
        self.assertRedirects(response, reverse("account:my_account"))

    def test_failed_logins_use_one_generic_message(self):
        active = user_with_password(username="known-active")
        inactive = user_with_password(username="known-inactive", is_active=False)
        cases = [
            (active.username, "wrong"),
            (inactive.username, PASSWORD),
            ("does-not-exist", PASSWORD),
        ]

        for username, password in cases:
            response = self.client.post(
                reverse("account:login"),
                {"username": username, "password": password},
                REMOTE_ADDR="192.0.2.10",
            )
            self.assertContains(
                response,
                "Incorrect username or password. Please try again.",
            )
            self.assertContains(response, 'role="alert"')
            self.assertContains(response, 'aria-describedby="login-error"', count=2)
            self.assertEqual(
                list(response.context["form"].non_field_errors()),
                ["Invalid username or password."],
            )

    def test_login_throttling_is_persisted_in_audit_events(self):
        username = "privacy-target"
        source = "192.0.2.44"
        for _ in range(5):
            response = self.client.post(
                reverse("account:login"),
                {"username": username, "password": "wrong"},
                REMOTE_ADDR=source,
            )
            self.assertEqual(response.status_code, 200)

        blocked = self.client.post(
            reverse("account:login"),
            {"username": username, "password": "wrong"},
            REMOTE_ADDR=source,
        )

        self.assertEqual(blocked.status_code, 429)
        events = AuditEvent.objects.filter(action__startswith="auth.login_")
        self.assertEqual(events.count(), 6)
        self.assertTrue(events.filter(action="auth.login_throttled").exists())
        for event in events:
            self.assertNotIn(username, str(event.metadata_json))
            self.assertNotIn(source, str(event.metadata_json))
