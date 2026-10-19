"""Lesson 2 is taught in three one-skill parts: 2.1 add/subtract (S2), 2.2 multiply (S3),
2.3 divide (S7). Each part ends in a 6-question exercise; the skill passes with 4 of 6.
Passing moves to the next part; failing gets support on that part's skill only."""

from django.urls import reverse

from apps.adaptive.models import Decision, DecisionTargetSkill
from apps.adaptive.services import skill_passed
from apps.curriculum.models import Lesson
from apps.feedback.models import SessionFeedback
from apps.learning.models import Session, StudentPath
from apps.learning.services.sessions import issue_session
from tests.integration._helpers import IntegrationSeededTestCase


class Lesson2PartTests(IntegrationSeededTestCase):
    def part(self, number):
        return Lesson.objects.get(unit_number=2, part_number=number)

    def start_regular(self, lesson):
        self.set_path(
            status=StudentPath.Status.LEARNING,
            stage=StudentPath.Stage.REGULAR,
            lesson=lesson,
        )
        return issue_session(
            actor=self.student,
            session_type=Session.SessionType.REGULAR,
            lesson=lesson,
        )

    def skill_codes(self, session):
        return set(session.items.values_list("question__skill__code", flat=True))

    def test_a_skill_passes_with_two_thirds_of_its_questions(self):
        self.assertTrue(skill_passed(3, 2))
        self.assertFalse(skill_passed(3, 1))
        self.assertTrue(skill_passed(6, 4))
        self.assertFalse(skill_passed(6, 3))

    def test_each_part_has_one_skill_and_a_six_question_exercise(self):
        for number, code in ((1, "S2"), (2, "S3"), (3, "S7")):
            lesson = self.part(number)
            with self.subTest(part=lesson.display_label):
                self.assertEqual(
                    list(lesson.lesson_skills.values_list("skill__code", flat=True)),
                    [code],
                )
                session = self.start_regular(lesson)
                self.assertEqual(session.items.count(), 6)
                self.assertEqual(self.skill_codes(session), {code})

    def test_passing_a_part_moves_on_to_the_next_part(self):
        session = self.start_regular(self.part(1))
        self.complete_session(session, correct_total=4)
        self.finalize_feedback(session)

        decision = Decision.objects.get(session=session)
        self.assertEqual(decision.action, Decision.Action.PROGRESS)
        self.assertEqual(decision.reason_code, "q_learning_argmax")
        self.assertRegex(decision.input_snapshot_json["state"], r"^\((\w+), \1, p\)$")
        self.path.refresh_from_db()
        self.assertEqual(self.path.current_lesson, self.part(2))
        self.assertEqual(self.path.current_stage, StudentPath.Stage.LESSON)
        self.assertIn(
            "continue to the next part of Lesson 2",
            SessionFeedback.objects.get(session=session).feedback_text,
        )

    def test_failing_a_part_stays_in_that_part_with_its_own_skill(self):
        lesson = self.part(2)
        session = self.start_regular(lesson)
        self.complete_session(session, correct_total=3)
        self.finalize_feedback(session)

        decision = Decision.objects.get(session=session)
        self.assertIn(
            decision.action,
            {Decision.Action.ADDITIONAL_EXERCISE, Decision.Action.FOUNDATIONAL_EXERCISE},
        )
        self.assertRegex(decision.input_snapshot_json["state"], r"^\((\w+), \1, f\)$")
        self.assertEqual(
            set(DecisionTargetSkill.objects.filter(decision=decision).values_list("skill__code", flat=True)),
            {"S3"},
        )
        self.path.refresh_from_db()
        self.assertEqual(self.path.current_lesson, lesson)
        follow_up = issue_session(
            actor=self.student,
            session_type=self.path.current_stage,
            lesson=lesson,
        )
        self.assertEqual(self.skill_codes(follow_up), {"S3"})

        # the part with assigned practice is still "You are here", not "Done"
        self.client.force_login(self.student)
        my_lesson = self.client.get(reverse("account:my_lesson"))
        self.assertContains(my_lesson, 'data-ui="lesson-part" data-state="current"', count=1)
        self.assertContains(my_lesson, 'data-ui="lesson-step" data-state="current" data-lesson="2"', count=1)

    def test_passing_the_last_part_moves_on_to_lesson_3(self):
        session = self.start_regular(self.part(3))
        self.complete_session(session)
        self.finalize_feedback(session)

        self.path.refresh_from_db()
        self.assertEqual(self.path.current_lesson.code, "L3-1")
        self.assertIn(
            "continue to the next lesson",
            SessionFeedback.objects.get(session=session).feedback_text,
        )

    def test_student_pages_group_the_parts_under_lesson_2(self):
        self.set_path(
            status=StudentPath.Status.LEARNING,
            stage=StudentPath.Stage.LESSON,
            lesson=self.part(2),
        )
        self.client.force_login(self.student)

        my_lesson = self.client.get(reverse("account:my_lesson"))
        self.assertContains(my_lesson, "Lesson 1 · 2 parts")
        self.assertContains(my_lesson, "Lesson 2 · 3 parts")
        self.assertContains(my_lesson, "Lesson 3 · 2 parts")
        self.assertContains(my_lesson, 'data-ui="lesson-part"', count=7)
        self.assertContains(my_lesson, 'data-ui="lesson-step"', count=6)

        dashboard = self.client.get(reverse("account:student_dashboard"))
        self.assertEqual(
            [step["label"] for step in dashboard.context["path_steps"]],
            ["Pretest", "Lesson 1", "Lesson 2", "Lesson 3", "Activity", "Posttest"],
        )
        lesson_2 = dashboard.context["path_steps"][2]
        self.assertEqual(lesson_2["state"], "current")
        self.assertEqual(lesson_2["detail"], "Lesson 2.2: Multiplying integers")

        page = self.client.get(reverse("learning:lesson", args=[self.part(2).slug]))
        self.assertContains(page, "Lesson 2.2</p>")
