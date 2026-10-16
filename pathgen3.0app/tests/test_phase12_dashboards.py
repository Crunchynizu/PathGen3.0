from html.parser import HTMLParser

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.classrooms.models import Classroom
from apps.learning.models import StudentPath
from tests.factories import (
    make_classroom,
    make_membership,
    make_student_path,
    make_system_setting,
    make_user,
)


class ChartPairParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.stack = []
        self.blocks = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if "data-chart-block" in attrs:
            block = {"canvas": 0, "table": 0}
            self.blocks.append(block)
            self.stack.append(block)
        elif self.stack and tag == "canvas":
            self.stack[-1]["canvas"] += 1
        elif self.stack and tag == "table":
            self.stack[-1]["table"] += 1

    def handle_endtag(self, tag):
        if tag == "article" and self.stack:
            self.stack.pop()


class Phase12DashboardTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_curriculum", verbosity=0)
        cls.admin = make_user(User.Role.ADMIN, username="phase12-admin")
        cls.teacher = make_user(User.Role.TEACHER, username="phase12-teacher")
        cls.other_teacher = make_user(User.Role.TEACHER, username="other-teacher")
        cls.student = make_user(
            User.Role.STUDENT,
            username="student-one",
            first_name="Ada",
            last_name="Learner",
        )
        cls.other_student = make_user(
            User.Role.STUDENT,
            username="student-two",
            first_name="Other",
            last_name="Student",
        )
        cls.classroom = make_classroom(code="MATH-7A", name="Math 7A", teacher=cls.teacher)
        cls.other_classroom = make_classroom(
            code="MATH-7B",
            name="Math 7B",
            teacher=cls.other_teacher,
        )
        make_membership(classroom=cls.classroom, student=cls.student, added_by=cls.admin)
        make_membership(classroom=cls.other_classroom, student=cls.other_student, added_by=cls.admin)
        make_student_path(student=cls.student)
        make_student_path(student=cls.other_student)
        make_system_setting(changed_by=cls.admin, study_access_enabled=True)

    def test_07_admin_dashboard_renders_seeded_data(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("portal:admin_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Research metrics")
        self.assertContains(response, "MATH-7A")

    def test_08_teacher_dashboard_renders_assigned_class_only(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("portal:teacher_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Math 7A")
        self.assertNotContains(response, "Math 7B")

    def test_09_student_dashboard_renders_self_only(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("account:student_dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ada Learner")
        self.assertNotContains(response, "Other Student")

    def test_10_student_view_does_not_expose_raw_p_known(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("account:student_dashboard"))
        content = response.content.decode()
        self.assertNotIn("p_known", content)
        self.assertNotIn("threshold", content.lower())

    def test_11_teacher_viewing_another_teachers_class_returns_404(self):
        self.client.force_login(self.teacher)
        response = self.client.get(
            reverse("portal:teacher_dashboard"),
            {"class": self.other_classroom.pk},
        )
        self.assertEqual(response.status_code, 404)

    def test_12_student_viewing_another_student_returns_404(self):
        self.client.force_login(self.student)
        response = self.client.get(
            reverse("portal:student_progress", args=[self.other_student.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_13_empty_state_is_distinct_from_zero(self):
        empty_class = make_classroom(code="EMPTY", name="Empty Class", teacher=self.teacher)
        self.client.force_login(self.admin)
        response = self.client.get(
            reverse("portal:admin_dashboard"),
            {"class": empty_class.pk},
        )
        self.assertContains(response, "No filter match")
        self.assertNotContains(response, ">0</p>", html=False)

    def test_14_every_rendered_chart_has_a_paired_table(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("portal:admin_dashboard"))
        parser = ChartPairParser()
        parser.feed(response.content.decode())
        self.assertEqual(len(parser.blocks), 5)
        for block in parser.blocks:
            self.assertEqual(block["table"], 1)
            self.assertLessEqual(block["canvas"], 1)
