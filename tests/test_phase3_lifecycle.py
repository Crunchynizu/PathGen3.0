from django.contrib.sessions.models import Session
from django.core.exceptions import PermissionDenied, ValidationError
from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.services.lifecycle import (
    create_account,
    deactivate_account,
    reactivate_account,
)
from apps.core.models import AuditEvent
from tests.factories import make_user


PASSWORD = "Existing!Password934"
NEW_PASSWORD = "Changed!Password583"


def user_with_password(role=User.Role.STUDENT, **overrides):
    user = make_user(role, **overrides)
    user.set_password(PASSWORD)
    user.save(update_fields=["password", "updated_at"])
    return user


class AccountLifecycleTests(TestCase):
    def setUp(self):
        self.admin = make_user(User.Role.ADMIN)

    def test_admin_create_deactivate_reactivate_are_audited(self):
        user = create_account(
            actor=self.admin,
            username="managed-student",
            role=User.Role.STUDENT,
            password=PASSWORD,
            first_name="Managed",
            last_name="Student",
        )
        deactivate_account(actor=self.admin, user_id=user.pk, reason="Enrollment ended")
        user.refresh_from_db()
        self.assertFalse(user.is_active)
        self.assertEqual(user.deactivated_by, self.admin)
        reactivate_account(actor=self.admin, user_id=user.pk)
        user.refresh_from_db()
        self.assertTrue(user.is_active)
        self.assertIsNone(user.deactivated_at)
        self.assertEqual(
            set(
                AuditEvent.objects.filter(target_id=user.pk).values_list(
                    "action", flat=True
                )
            ),
            {"account.created", "account.deactivated", "account.reactivated"},
        )

    def test_deactivation_invalidates_all_user_sessions(self):
        user = user_with_password()
        clients = [Client(), Client()]
        session_keys = []
        for client in clients:
            client.force_login(user)
            session_keys.append(client.session.session_key)

        deactivate_account(actor=self.admin, user_id=user.pk, reason="Access removed")

        self.assertFalse(Session.objects.filter(session_key__in=session_keys).exists())
        for client in clients:
            self.assertRedirects(
                client.get(reverse("account:my_account")),
                reverse("account:login") + "?next=" + reverse("account:my_account"),
            )

    def test_admin_accounts_cannot_use_normal_lifecycle(self):
        with self.assertRaises(ValueError):
            create_account(
                actor=self.admin,
                username="second-admin",
                role=User.Role.ADMIN,
                password=PASSWORD,
            )
        with self.assertRaises(PermissionDenied):
            deactivate_account(
                actor=self.admin,
                user_id=self.admin.pk,
                reason="Not permitted",
            )

    def test_account_creation_enforces_password_validation(self):
        with self.assertRaises(ValidationError):
            create_account(
                actor=self.admin,
                username="weak-password",
                role=User.Role.STUDENT,
                password="123",
            )

    def test_username_and_role_are_immutable(self):
        user = make_user()
        user.username = "changed"
        with self.assertRaises(ValidationError):
            user.save()
        user.refresh_from_db()
        user.role = User.Role.TEACHER
        with self.assertRaises(ValidationError):
            user.save()

    def test_name_change_is_self_only_and_audited(self):
        user = user_with_password()
        self.client.force_login(user)
        response = self.client.post(
            reverse("account:update_name"),
            {"first_name": "New", "last_name": "Name"},
        )
        self.assertRedirects(response, reverse("account:my_account"))
        user.refresh_from_db()
        self.assertEqual((user.first_name, user.last_name), ("New", "Name"))
        self.assertTrue(
            AuditEvent.objects.filter(
                action="account.name_changed", actor=user, target_id=user.pk
            ).exists()
        )

    def test_password_change_rotates_current_and_invalidates_other_sessions(self):
        user = user_with_password()
        current = Client()
        other = Client()
        current.force_login(user)
        other.force_login(user)
        old_current_key = current.session.session_key
        other_key = other.session.session_key

        response = current.post(
            reverse("account:update_password"),
            {
                "old_password": PASSWORD,
                "new_password1": NEW_PASSWORD,
                "new_password2": NEW_PASSWORD,
            },
        )

        self.assertRedirects(response, reverse("account:my_account"))
        self.assertNotEqual(current.session.session_key, old_current_key)
        self.assertEqual(current.get(reverse("account:my_account")).status_code, 200)
        self.assertFalse(Session.objects.filter(session_key=other_key).exists())
        self.assertTrue(user.__class__.objects.get(pk=user.pk).check_password(NEW_PASSWORD))
        self.assertTrue(
            AuditEvent.objects.filter(
                action="account.password_changed", target_id=user.pk
            ).exists()
        )


class LogoutSecurityTests(TestCase):
    def test_get_only_confirms_and_post_requires_csrf(self):
        user = user_with_password()
        client = Client(enforce_csrf_checks=True)
        client.force_login(user)

        confirmation = client.get(reverse("account:logout"))
        self.assertEqual(confirmation.status_code, 200)
        self.assertEqual(client.get(reverse("account:my_account")).status_code, 200)
        self.assertEqual(client.post(reverse("account:logout")).status_code, 403)

        token = client.cookies["csrftoken"].value
        response = client.post(
            reverse("account:logout"),
            HTTP_X_CSRFTOKEN=token,
        )
        self.assertRedirects(response, reverse("account:login"))
        self.assertTrue(
            AuditEvent.objects.filter(action="auth.logout", target_id=user.pk).exists()
        )
