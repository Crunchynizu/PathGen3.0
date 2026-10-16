from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.selectors import get_scoped_user_or_404, users_visible_to
from apps.accounts.services.lifecycle import create_account
from apps.classrooms.selectors import get_scoped_classroom_or_404
from apps.learning.selectors import get_scoped_session_or_404
from tests.factories import make_classroom, make_membership, make_session, make_user


class RolePermissionTests(TestCase):
    def test_dashboard_role_matrix(self):
        users = {
            User.Role.ADMIN: make_user(User.Role.ADMIN),
            User.Role.TEACHER: make_user(User.Role.TEACHER),
            User.Role.STUDENT: make_user(User.Role.STUDENT),
        }
        endpoints = {
            User.Role.ADMIN: "account:admin_dashboard",
            User.Role.TEACHER: "account:teacher_dashboard",
            User.Role.STUDENT: "account:student_dashboard",
        }

        for role, user in users.items():
            self.client.force_login(user)
            for endpoint_role, endpoint in endpoints.items():
                with self.subTest(role=role, endpoint=endpoint_role):
                    response = self.client.get(reverse(endpoint))
                    self.assertEqual(response.status_code, 200 if role == endpoint_role else 403)
            self.client.logout()

    def test_anonymous_role_route_redirects_to_login(self):
        response = self.client.get(reverse("account:student_dashboard"))
        self.assertRedirects(
            response,
            reverse("account:login") + "?next=" + reverse("account:student_dashboard"),
        )

    def test_teacher_and_student_cannot_create_accounts(self):
        for role in (User.Role.TEACHER, User.Role.STUDENT):
            with self.subTest(role=role), self.assertRaises(PermissionDenied):
                create_account(
                    actor=make_user(role),
                    username=f"created-by-{role}",
                    role=User.Role.STUDENT,
                    password="Strong!Password934",
                )


class ScopedSelectorTests(TestCase):
    def setUp(self):
        self.admin = make_user(User.Role.ADMIN)
        self.teacher = make_user(User.Role.TEACHER)
        self.other_teacher = make_user(User.Role.TEACHER)
        self.student = make_user(User.Role.STUDENT)
        self.outsider = make_user(User.Role.STUDENT)
        self.classroom = make_classroom(teacher=self.teacher)
        self.other_classroom = make_classroom(teacher=self.other_teacher)
        make_membership(self.classroom, self.student, self.admin)
        make_membership(self.other_classroom, self.outsider, self.admin)
        self.session = make_session(student=self.student)
        self.outside_session = make_session(student=self.outsider)

    def test_teacher_scope_is_applied_before_user_lookup(self):
        visible_ids = set(users_visible_to(self.teacher).values_list("pk", flat=True))
        self.assertEqual(visible_ids, {self.teacher.pk, self.student.pk})
        self.assertEqual(
            get_scoped_user_or_404(actor=self.teacher, user_id=self.student.pk),
            self.student,
        )
        with self.assertRaises(Http404):
            get_scoped_user_or_404(actor=self.teacher, user_id=self.outsider.pk)

    def test_classroom_and_evidence_reads_are_scoped(self):
        self.assertEqual(
            get_scoped_classroom_or_404(actor=self.teacher, classroom_id=self.classroom.pk),
            self.classroom,
        )
        self.assertEqual(
            get_scoped_session_or_404(actor=self.teacher, session_id=self.session.pk),
            self.session,
        )
        with self.assertRaises(Http404):
            get_scoped_classroom_or_404(
                actor=self.teacher,
                classroom_id=self.other_classroom.pk,
            )
        with self.assertRaises(Http404):
            get_scoped_session_or_404(
                actor=self.teacher,
                session_id=self.outside_session.pk,
            )

    def test_student_can_only_select_own_objects(self):
        self.assertEqual(
            get_scoped_user_or_404(actor=self.student, user_id=self.student.pk),
            self.student,
        )
        self.assertEqual(
            get_scoped_session_or_404(actor=self.student, session_id=self.session.pk),
            self.session,
        )
        with self.assertRaises(Http404):
            get_scoped_user_or_404(actor=self.student, user_id=self.outsider.pk)
        with self.assertRaises(Http404):
            get_scoped_session_or_404(
                actor=self.student,
                session_id=self.outside_session.pk,
            )
