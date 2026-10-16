import hashlib
import io
import json
from collections import Counter
from pathlib import Path

from django.conf import settings
from django.core.management import call_command
from django.db.models import Count, Q
from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.curriculum.models import (
    Lesson,
    Question,
    QuestionChoice,
    QuestionSet,
    QuestionSetItem,
    Skill,
    Video,
)
from apps.curriculum.source import validate_curriculum_source
from tests.factories import make_user


class CurriculumSourceTests(SimpleTestCase):
    def test_source_contract_and_pdf_hash_pass(self):
        summary = validate_curriculum_source()
        self.assertEqual(summary["questions_total"], 121)
        self.assertEqual((summary["lessons"], summary["lesson_units"], summary["skills"]), (5, 3, 7))
        self.assertEqual(
            {key: summary[key] for key in ("regular", "additional", "foundational", "activity", "prepost")},
            {"regular": 30, "additional": 30, "foundational": 21, "activity": 10, "prepost": 30},
        )

    def test_prepost_rewrite_and_fixed_order(self):
        root = Path(settings.BASE_DIR) / "content_source"
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        prepost = json.loads((root / "pretest_posttest.json").read_text(encoding="utf-8"))
        questions = prepost["question_set"]["questions"]
        self.assertEqual([question["code"] for question in questions], [f"PP-{number:02d}" for number in range(1, 31)])
        rewrite = manifest["prepost_rewrites"][0]
        self.assertEqual(rewrite["code"], "PP-13")
        self.assertEqual(questions[12]["prompt"], rewrite["new_prompt"])
        self.assertEqual(questions[12]["correct_answer"], rewrite["new_key"])
        self.assertTrue(all(question["presentation_type"] == "text" for question in questions))

    def test_activity_distribution_and_bloom_contract(self):
        activity = json.loads(
            (Path(settings.BASE_DIR) / "content_source" / "activity.json").read_text(encoding="utf-8")
        )["question_set"]["questions"]
        self.assertEqual(
            Counter(question["skill_code"] for question in activity),
            Counter({"S1": 2, "S2": 2, "S3": 1, "S4": 2, "S5": 1, "S6": 1, "S7": 1}),
        )
        self.assertEqual(Counter(question["bloom_band"] for question in activity), Counter({"LOTS": 6, "HOTS": 4}))

    def test_static_asset_inventory(self):
        root = Path(settings.BASE_DIR) / "static"
        self.assertEqual({path.name for path in (root / "avatar").glob("*.png")}, {"student_avatar.png", "teacher_avatar.png", "admin_avatar.png"})
        self.assertEqual({path.name for path in (root / "logo").glob("*.png")}, {"pathgen.png"})
        self.assertFalse((root / "pretest_posttest").exists())

    def test_prepost_pdf_hash_is_exact(self):
        root = Path(settings.BASE_DIR)
        manifest = json.loads((root / "content_source" / "manifest.json").read_text(encoding="utf-8"))
        digest = hashlib.sha256((root.parent / "pathgen3.0docs" / "content" / "pretest_posttest.pdf").read_bytes()).hexdigest()
        self.assertEqual(digest, manifest["pretest_posttest_sha256"])


class CurriculumSeedAndPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_curriculum", stdout=io.StringIO())
        cls.admin = make_user(User.Role.ADMIN)
        cls.teacher = make_user(User.Role.TEACHER)
        cls.student = make_user(User.Role.STUDENT)

    def test_seeded_database_counts_and_choice_contract(self):
        self.assertEqual(Skill.objects.count(), 7)
        self.assertEqual(Lesson.objects.count(), 5)
        self.assertEqual(Video.objects.count(), 4)
        self.assertEqual(Question.objects.count(), 121)
        self.assertEqual(QuestionChoice.objects.count(), 484)
        self.assertEqual(QuestionSet.objects.count(), 19)
        self.assertEqual(QuestionSetItem.objects.count(), 121)
        self.assertFalse(
            Question.objects.annotate(choice_total=Count("choices")).exclude(choice_total=4).exists()
        )
        self.assertFalse(
            Question.objects.annotate(correct_total=Count("choices", filter=Q(choices__is_correct=True))).exclude(correct_total=1).exists()
        )

    def test_seed_is_idempotent(self):
        output = io.StringIO()
        call_command("seed_curriculum", stdout=output)
        self.assertIn("Created: skills=0, lessons=0, videos=0, questions=0, choices=0, sets=0, items=0", output.getvalue())
        self.assertEqual(Question.objects.count(), 121)

    def test_admin_and_teacher_content_pages_render(self):
        pages = [
            ("curriculum:content", "pages/shared/content.html"),
            ("curriculum:view_lessons", "pages/shared/view_lesson.html"),
            ("curriculum:view_questions", "pages/shared/view_questions.html"),
        ]
        for user in (self.admin, self.teacher):
            self.client.force_login(user)
            for route, template in pages:
                with self.subTest(role=user.role, route=route):
                    response = self.client.get(reverse(route))
                    self.assertEqual(response.status_code, 200)
                    self.assertTemplateUsed(response, template)
                    self.assertTemplateUsed(response, "_base.html")

    def test_student_cannot_browse_staff_content(self):
        self.client.force_login(self.student)
        for route in ("curriculum:content", "curriculum:view_lessons", "curriculum:view_questions"):
            with self.subTest(route=route):
                self.assertEqual(self.client.get(reverse(route)).status_code, 403)

    def test_prepost_is_excluded_and_keys_are_not_rendered(self):
        self.client.force_login(self.teacher)
        response = self.client.get(reverse("curriculum:view_questions"))
        self.assertNotContains(response, "PP-01")
        self.assertNotContains(response, "Protected Pre-test / Post-test")
        self.assertNotContains(response, "is_correct")
        self.assertEqual(response.context["question_sets"].filter(set_type=QuestionSet.SetType.PREPOST).count(), 0)
