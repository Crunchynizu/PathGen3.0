from django.core.management import call_command
from django.db import DatabaseError, transaction
from django.test import Client, TestCase
from django.urls import reverse
from django.utils.html import escape

from apps.accounts.models import User
from apps.adaptive.models import Decision, MasteryEvent
from apps.core.models import AuditEvent
from apps.curriculum.models import QuestionChoice
from apps.learning.models import Session, StudentPath
from tests.factories import (
    make_audit_event,
    make_choice,
    make_classroom,
    make_decision,
    make_feedback,
    make_mastery_event,
    make_membership,
    make_question,
    make_response,
    make_session,
    make_session_item,
    make_student_path,
    make_system_setting,
    make_user,
)


PASSWORD = "Phase13!SecurePassword"


def set_password(user, password=PASSWORD):
    user.set_password(password)
    user.save(update_fields=["password", "updated_at"])
    return user


class Phase13SecurityTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_curriculum", verbosity=0)
        cls.admin = set_password(make_user(User.Role.ADMIN, username="phase13-admin"))
        cls.teacher_a = set_password(
            make_user(User.Role.TEACHER, username="phase13-teacher-a")
        )
        cls.teacher_b = set_password(
            make_user(User.Role.TEACHER, username="phase13-teacher-b")
        )
        cls.student_a = set_password(
            make_user(User.Role.STUDENT, username="phase13-student-a")
        )
        cls.student_b = set_password(
            make_user(User.Role.STUDENT, username="phase13-student-b")
        )
        cls.class_a = make_classroom(code="P13-A", teacher=cls.teacher_a)
        cls.class_b = make_classroom(code="P13-B", teacher=cls.teacher_b)
        make_membership(
            classroom=cls.class_a, student=cls.student_a, added_by=cls.admin
        )
        make_membership(
            classroom=cls.class_b, student=cls.student_b, added_by=cls.admin
        )
        make_student_path(student=cls.student_a)
        make_student_path(student=cls.student_b)
        make_system_setting(
            changed_by=cls.admin,
            study_access_enabled=True,
            posttest_access_enabled=True,
        )

        cls.other_session = make_session(
            student=cls.student_b,
            session_type=Session.SessionType.PRETEST,
            status=Session.Status.ISSUED,
        )
        question = make_question(
            is_published=True,
            feedback_correct="PREPOST_CORRECT_FEEDBACK_MUST_NOT_RENDER",
            feedback_incorrect="PREPOST_INCORRECT_FEEDBACK_MUST_NOT_RENDER",
            explanation="PREPOST_EXPLANATION_MUST_NOT_RENDER",
        )
        cls.other_item = make_session_item(
            session=cls.other_session, question=question
        )
        cls.other_choice = make_choice(
            question=question,
            label=QuestionChoice.Label.A,
            text="A visible assessment choice",
            is_correct=True,
        )
        cls.submitted_response = make_response(
            session_item=cls.other_item,
            selected_choice=cls.other_choice,
        )

    def test_01_teacher_cannot_read_other_teachers_class_detail(self):
        self.client.force_login(self.teacher_a)
        response = self.client.get(
            reverse("portal:class_detail", args=[self.class_b.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_02_teacher_cannot_read_student_in_other_teachers_class(self):
        self.client.force_login(self.teacher_a)
        response = self.client.get(
            reverse("portal:student_progress", args=[self.student_b.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_03_student_cannot_read_another_students_dashboard(self):
        self.client.force_login(self.student_a)
        response = self.client.get(
            reverse("portal:student_progress", args=[self.student_b.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_04_student_cannot_read_another_students_session(self):
        self.client.force_login(self.student_a)
        response = self.client.get(
            reverse("learning:assessment_session", args=[self.other_session.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_05_admin_cannot_modify_a_submitted_response(self):
        self.client.force_login(self.admin)
        response = self.client.post(
            reverse("learning:submit_response", args=[self.other_session.pk]),
            {
                "session_item": self.other_item.pk,
                "choice": self.other_choice.pk,
            },
        )
        self.assertEqual(response.status_code, 403)

    def _assert_append_only_for_every_role(self, factory, model, update_values):
        for role in (User.Role.ADMIN, User.Role.TEACHER, User.Role.STUDENT):
            with self.subTest(role=role):
                actor = make_user(role)
                row = factory(actor) if model is AuditEvent else factory()
                with self.assertRaises(DatabaseError):
                    with transaction.atomic():
                        model.objects.filter(pk=row.pk).update(**update_values)

    def test_06_any_role_cannot_modify_adaptive_mastery_event(self):
        self._assert_append_only_for_every_role(
            lambda _actor=None: make_mastery_event(),
            MasteryEvent,
            {"p_before": "0.200000"},
        )

    def test_07_any_role_cannot_modify_adaptive_decision(self):
        self._assert_append_only_for_every_role(
            lambda _actor=None: make_decision(),
            Decision,
            {"reason_code": "tampered"},
        )

    def test_08_any_role_cannot_modify_core_audit_event(self):
        self._assert_append_only_for_every_role(
            lambda actor: make_audit_event(actor=actor),
            AuditEvent,
            {"action": "tampered"},
        )

    def test_09_unauthenticated_protected_routes_redirect_to_login(self):
        protected_urls = [
            reverse("account:my_account"),
            reverse("account:student_dashboard"),
            reverse("portal:admin_dashboard"),
            reverse("portal:teacher_dashboard"),
            reverse("portal:class_detail", args=[self.class_a.pk]),
            reverse("portal:student_progress", args=[self.student_a.pk]),
            reverse("learning:assessment_session", args=[self.other_session.pk]),
        ]
        for url in protected_urls:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse("account:login"), response.url)

    def test_10_logout_get_returns_method_not_allowed(self):
        self.client.force_login(self.student_a)
        response = self.client.get(reverse("account:logout"))
        self.assertEqual(response.status_code, 405)

    def test_11_login_post_without_csrf_is_rejected(self):
        csrf_client = Client(enforce_csrf_checks=True)
        response = csrf_client.post(
            reverse("account:login"),
            {"username": self.student_a.username, "password": PASSWORD},
        )
        self.assertEqual(response.status_code, 403)

    def test_12_feedback_text_is_escaped_everywhere_it_is_rendered(self):
        unsafe = '<script data-test="phase13">alert("xss")</script>'
        session = make_session(
            student=self.student_a,
            session_type=Session.SessionType.REGULAR,
            status=Session.Status.COMPLETED,
            lesson_id=None,
        )
        make_feedback(session=session, feedback_text=unsafe)

        self.client.force_login(self.student_a)
        student_response = self.client.get(reverse("account:student_dashboard"))
        self.assertNotContains(student_response, unsafe, html=False)
        self.assertContains(student_response, escape(unsafe), html=False)

        self.client.force_login(self.admin)
        progress_response = self.client.get(
            reverse("portal:student_progress", args=[self.student_a.pk])
        )
        self.assertNotContains(progress_response, unsafe, html=False)
        self.assertContains(progress_response, escape(unsafe), html=False)

    def test_13_throttling_blocks_the_sixth_failed_login(self):
        source = "192.0.2.113"
        for _ in range(5):
            response = self.client.post(
                reverse("account:login"),
                {"username": "phase13-unknown", "password": "wrong"},
                REMOTE_ADDR=source,
            )
            self.assertEqual(response.status_code, 200)
        blocked = self.client.post(
            reverse("account:login"),
            {"username": "phase13-unknown", "password": "wrong"},
            REMOTE_ADDR=source,
        )
        self.assertEqual(blocked.status_code, 429)

    def test_14_throttling_does_not_block_a_successful_login(self):
        source = "192.0.2.114"
        for _ in range(5):
            self.client.post(
                reverse("account:login"),
                {"username": self.student_a.username, "password": "wrong"},
                REMOTE_ADDR=source,
            )
        response = self.client.post(
            reverse("account:login"),
            {"username": self.student_a.username, "password": PASSWORD},
            REMOTE_ADDR=source,
        )
        self.assertRedirects(response, reverse("account:student_dashboard"))

    def test_15_prepost_answer_key_is_not_in_student_facing_response(self):
        self.client.force_login(self.student_b)
        # Every item is answered, so the view no longer renders an empty question
        # form; it redirects. Whatever page the student lands on must not leak keys.
        response = self.client.get(
            reverse("learning:assessment_session", args=[self.other_session.pk]),
            follow=True,
        )
        content = response.content.decode()
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("PREPOST_CORRECT_FEEDBACK_MUST_NOT_RENDER", content)
        self.assertNotIn("PREPOST_INCORRECT_FEEDBACK_MUST_NOT_RENDER", content)
        self.assertNotIn("PREPOST_EXPLANATION_MUST_NOT_RENDER", content)
        self.assertNotIn("data-correct", content)
        self.assertNotIn("correct answer", content.lower())
