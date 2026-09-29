import io

from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.curriculum.models import Lesson
from apps.learning.models import StudentPath
from tests.factories import make_student_path, make_user


class AdminStudentListTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = make_user(User.Role.ADMIN)
        cls.teacher = make_user(User.Role.TEACHER)
        cls.student = make_user(
            User.Role.STUDENT, username="juan_student", first_name="Juan", last_name="Cruz"
        )

    def test_admin_get(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin:student_list"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/admin/student_list.html")
        self.assertContains(response, 'data-ui="student-row"')

    def test_teacher_get_is_404(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(reverse("admin:student_list")).status_code, 404)

    def test_student_get_is_404(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(reverse("admin:student_list")).status_code, 404)

    def test_anonymous_redirects_to_login(self):
        response = self.client.get(reverse("admin:student_list"))
        self.assertEqual(response.status_code, 302)
        self.assertIn("/account/login/", response["Location"])

    def test_list_renders_seeded_students_and_progress_link(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin:student_list"))
        self.assertContains(response, "Juan Cruz")
        self.assertContains(response, "juan_student")
        self.assertContains(response, reverse("portal:student_progress", args=[self.student.pk]))
        self.assertContains(response, "avatar/student_avatar.png")
        self.assertContains(response, "Not enough evidence")
        self.assertNotContains(response, "p_known")

    def test_search_filters_by_username(self):
        make_user(User.Role.STUDENT, username="other_student", first_name="Other")
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin:student_list"), {"q": "juan_student"})
        self.assertEqual(response.context["page_obj"].paginator.count, 1)
        self.assertContains(response, "Juan Cruz")
        self.assertNotContains(response, "other_student")

    def test_account_and_path_status_filters(self):
        other = make_user(User.Role.STUDENT, username="inactive_student", is_active=False)
        make_student_path(student=self.student, status=StudentPath.Status.LEARNING)
        make_student_path(student=other, status=StudentPath.Status.PRETEST_REQUIRED)
        self.client.force_login(self.admin)
        active = self.client.get(reverse("admin:student_list"), {"status": "active"})
        inactive = self.client.get(reverse("admin:student_list"), {"status": "inactive"})
        learning = self.client.get(reverse("admin:student_list"), {"path": "learning"})
        self.assertEqual(active.context["page_obj"].paginator.count, 1)
        self.assertEqual(inactive.context["page_obj"].paginator.count, 1)
        self.assertEqual(learning.context["page_obj"].paginator.count, 1)
        self.assertContains(learning, "juan_student")
        self.assertNotContains(learning, "inactive_student")

    def test_pagination_limits_to_25_and_validates_page(self):
        for number in range(26):
            make_user(User.Role.STUDENT, username=f"student_{number:02d}")
        self.client.force_login(self.admin)
        first = self.client.get(reverse("admin:student_list"))
        second = self.client.get(reverse("admin:student_list"), {"page": "2"})
        invalid = self.client.get(reverse("admin:student_list"), {"page": "invalid"})
        self.assertEqual(len(first.context["rows"]), 25)
        self.assertEqual(len(second.context["rows"]), 2)
        self.assertEqual(invalid.context["page_obj"].number, 1)

    def test_empty_state_with_zero_students(self):
        self.student.delete()
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin:student_list"))
        self.assertContains(response, "No students yet")
        self.assertNotContains(response, "No matching students")

    def test_filter_no_match_is_distinct_from_empty(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("admin:student_list"), {"q": "does-not-exist"})
        self.assertContains(response, "No matching students")
        self.assertNotContains(response, "No students yet")

    def test_sidebar_link_only_for_admin(self):
        self.client.force_login(self.admin)
        self.assertContains(self.client.get(reverse("admin:student_list")), 'href="/admin/students/"')
        self.client.force_login(self.teacher)
        self.assertNotContains(self.client.get(reverse("portal:teacher_dashboard")), 'href="/admin/students/"')


class PublishedLessonDetailTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_curriculum", stdout=io.StringIO())
        cls.admin = make_user(User.Role.ADMIN)
        cls.teacher = make_user(User.Role.TEACHER)
        cls.student = make_user(User.Role.STUDENT)

    def url(self, code="L1"):
        return reverse("curriculum:view_lesson_detail", args=[code])

    def test_admin_get(self):
        self.client.force_login(self.admin)
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "pages/shared/view_lesson.detail.html")
        self.assertContains(response, "Understanding and representing integers")

    def test_teacher_get(self):
        self.client.force_login(self.teacher)
        self.assertEqual(self.client.get(self.url()).status_code, 200)

    def test_student_get_is_404(self):
        self.client.force_login(self.student)
        self.assertEqual(self.client.get(self.url()).status_code, 404)

    def test_anonymous_redirects_to_login(self):
        response = self.client.get(self.url())
        self.assertEqual(response.status_code, 302)
        self.assertIn("/account/login/", response["Location"])

    def test_renders_all_block_types(self):
        lesson = Lesson.objects.get(code="L1")
        content = lesson.content_json
        content["blocks"] += [
            {"type": "heading", "text": "Extra heading"},
            {"type": "subheading", "text": "Extra subheading"},
            {"type": "paragraph", "text": "Extra paragraph"},
            {"type": "bullet_list", "items": ["Bullet marker"]},
            {"type": "numbered_list", "items": ["Numbered marker"]},
            {"type": "worked_example", "title": "Example marker", "steps": ["Step marker"]},
            {"type": "common_mistake", "text": "Mistake marker"},
            {"type": "callout", "text": "Callout marker"},
        ]
        lesson.content_json = content
        lesson.save(update_fields=["content_json"])
        self.client.force_login(self.teacher)
        response = self.client.get(self.url())
        for marker in (
            "Extra heading", "Extra subheading", "Extra paragraph", "Bullet marker",
            "Numbered marker", "Example marker", "Step marker", "Mistake marker",
            "Callout marker", "integer-number-line.png", "youtube-nocookie.com",
        ):
            with self.subTest(marker=marker):
                self.assertContains(response, marker)

    def test_never_exposes_prepost_content_or_answer_keys(self):
        self.client.force_login(self.teacher)
        response = self.client.get(self.url())
        self.assertNotContains(response, "PP-")
        self.assertNotContains(response, "is_correct")
        self.assertTrue(all(question_set.set_type != "prepost" for question_set in response.context["question_sets"]))

    def test_video_uses_youtube_nocookie_and_segment_bounds(self):
        self.client.force_login(self.teacher)
        response = self.client.get(self.url())
        self.assertContains(response, "https://www.youtube-nocookie.com/embed/")
        self.assertContains(response, "start=60&amp;end=110")

    def test_unpublished_lesson_is_404_and_navigation_is_published_only(self):
        Lesson.objects.filter(code="L2").update(is_published=False)
        self.client.force_login(self.admin)
        self.assertEqual(self.client.get(self.url("L2")).status_code, 404)
        response = self.client.get(self.url())
        self.assertNotContains(response, self.url("L2"))
        self.assertContains(response, self.url("L3"))
