import re

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
            "portal:admin_dashboard": "pages/admin/admin_dashboard.html",
            "portal:user_management": "pages/admin/user_management.html",
            "portal:class_management": "pages/admin/class_management.html",
            "portal:override": "pages/admin/override.html",
            "portal:audit_logs": "pages/admin/audit_logs.html",
        }
        for route, template in pages.items():
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template)

    def test_every_teacher_page_renders(self):
        self.client.force_login(self.teacher)
        pages = [
            (
                reverse("portal:teacher_dashboard"),
                "pages/teacher/teacher_dashboard.html",
            ),
            (reverse("portal:my_classes"), "pages/teacher/my_class.html"),
            (
                reverse("portal:class_detail", args=[self.classroom.pk]),
                "pages/shared/view_class_detail.html",
            ),
        ]
        for url, template in pages:
            with self.subTest(url=url):
                response = self.client.get(url)
                self.assertEqual(response.status_code, 200)
                self.assertTemplateUsed(response, template)

    def test_admin_reaches_the_shared_class_detail(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("portal:class_detail", args=[self.classroom.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/shared/view_class_detail.html")
        self.assertContains(response, "Classes")
        self.assertEqual(response.context["back_url"], reverse("portal:class_management"))

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
        expected_main = {
            User.Role.ADMIN: ["Dashboard", "Users", "Classes", "Content", "Overrides", "Audit Logs"],
            User.Role.TEACHER: ["Dashboard", "My Classes", "Content"],
            User.Role.STUDENT: ["Dashboard", "My Lesson"],
        }
        for role, labels in expected.items():
            with self.subTest(role=role):
                user = make_user(role)
                self.client.force_login(user)
                response = self.client.get(reverse("account:my_account"))
                self.assertEqual(response.status_code, 200)
                for label in labels:
                    self.assertContains(response, label)
                main_nav = re.search(
                    r'<nav\b[^>]*aria-label="Main"[^>]*>(.*?)</nav>',
                    response.content.decode("utf-8"),
                    re.S,
                )
                self.assertIsNotNone(main_nav)
                visible_destinations = re.findall(
                    r'>(Dashboard|Users|Classes|My Classes|Content|Overrides|Audit Logs|My Lesson)</a>',
                    main_nav.group(1),
                )
                self.assertEqual(visible_destinations, expected_main[role])
