from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from tests.factories import make_classroom, make_user


class PhaseFourPageTests(TestCase):
    def setUp(self):
        self.admin = make_user(User.Role.ADMIN)
        self.teacher = make_user(User.Role.TEACHER)
        self.classroom = make_classroom(teacher=self.teacher)

    def test_every_admin_page_renders(self):
        self.client.force_login(self.admin)
        pages = {
            "portal:admin_dashboard": "admin/admin_dashboard.html",
            "portal:user_management": "admin/user_management.html",
            "portal:class_management": "admin/class_management.html",
            "portal:override": "admin/override.html",
            "portal:audit_logs": "admin/audit_logs.html",
        }
        for route, template in pages.items():
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template)

    def test_every_teacher_page_renders(self):
        self.client.force_login(self.teacher)
        pages = [
            (reverse("portal:teacher_dashboard"), "teacher/teacher_dashboard.html"),
            (reverse("portal:my_classes"), "teacher/my_class.html"),
            (
                reverse("portal:class_detail", args=[self.classroom.pk]),
                "teacher/class_detail.html",
            ),
        ]
        for url, template in pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template)

    def test_sidebar_uses_exact_role_labels(self):
        expected = {
            User.Role.ADMIN: [
                "Dashboard",
                "Users",
                "Classes",
                "Content",
                "Overrides",
                "Audit Logs",
                "My Account",
                "Logout",
            ],
            User.Role.TEACHER: [
                "Dashboard",
                "My Classes",
                "Content",
                "My Account",
                "Logout",
            ],
            User.Role.STUDENT: ["Dashboard", "My Lesson", "My Account", "Logout"],
        }
        for role, labels in expected.items():
            with self.subTest(role=role):
                user = make_user(role)
                self.client.force_login(user)
                response = self.client.get(reverse("account:my_account"))
                self.assertEqual(response.status_code, 200)
                for label in labels:
                    self.assertContains(response, label)
