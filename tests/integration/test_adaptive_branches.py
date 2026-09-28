from unittest.mock import patch

from django.utils import timezone

from apps.adaptive.models import Decision, DecisionTargetSkill
from apps.curriculum.models import QuestionSet
from apps.learning.models import Response, Session, SessionItem, StudentPath
from apps.learning.services.sessions import issue_session
from tests.integration._helpers import IntegrationSeededTestCase


class AdaptiveBranchAcceptanceTests(IntegrationSeededTestCase):
    def start_lesson_one_regular(self):
        lesson = self.lesson(1)
        self.set_path(
            status=StudentPath.Status.LEARNING,
            stage=StudentPath.Stage.REGULAR,
            lesson=lesson,
        )
        return lesson, issue_session(
            actor=self.student,
            session_type=Session.SessionType.REGULAR,
            lesson=lesson,
        )

    def one_weak_skill_scores(self, session, *, weak_code="S1", weak_correct=0):
        skill_codes = set(
            session.items.values_list("question__skill__code", flat=True)
        )
        self.assertIn(weak_code, skill_codes)
        return {
            code: weak_correct if code == weak_code else 3
            for code in skill_codes
        }

    def test_branch_a_additional_exercise_then_q_learning_runs_again(self):
        lesson, regular = self.start_lesson_one_regular()
        with patch(
            "apps.adaptive.services.decide",
            return_value=(
                Decision.Action.ADDITIONAL_EXERCISE,
                "q_learning_argmax",
            ),
        ) as regular_decide:
            self.complete_session(
                regular,
                correct_per_skill=self.one_weak_skill_scores(
                    regular,
                    weak_correct=1,
                ),
            )
        regular_decide.assert_called_once()
        self.finalize_feedback(regular)

        first_decision = Decision.objects.get(session=regular)
        self.path.refresh_from_db()
        self.assertEqual(
            first_decision.action,
            Decision.Action.ADDITIONAL_EXERCISE,
        )
        self.assertEqual(self.path.current_lesson, lesson)
        self.assertEqual(self.path.current_stage, StudentPath.Stage.ADDITIONAL)

        additional = issue_session(
            actor=self.student,
            session_type=Session.SessionType.ADDITIONAL,
            lesson=lesson,
        )
        self.assertEqual(additional.items.count(), 6)
        with patch(
            "apps.adaptive.services.decide",
            return_value=(Decision.Action.PROGRESS, "q_learning_argmax"),
        ) as additional_decide:
            self.complete_session(additional)
        additional_decide.assert_called_once()
        self.finalize_feedback(additional)
        self.assertEqual(Decision.objects.filter(session=additional).count(), 1)

    def test_branch_b_foundational_is_fixed_progress_with_follow_up(self):
        lesson, regular = self.start_lesson_one_regular()
        with patch(
            "apps.adaptive.services.decide",
            return_value=(
                Decision.Action.FOUNDATIONAL_EXERCISE,
                "q_learning_argmax",
            ),
        ):
            self.complete_session(
                regular,
                correct_per_skill=self.one_weak_skill_scores(regular),
            )
        self.finalize_feedback(regular)
        regular_decision = Decision.objects.get(session=regular)
        self.assertTrue(
            regular_decision.target_skills.filter(
                skill__code="S1",
                target_kind=DecisionTargetSkill.TargetKind.NEXT_EXERCISE,
            ).exists()
        )

        self.path.refresh_from_db()
        self.assertEqual(self.path.current_lesson, lesson)
        self.assertEqual(self.path.current_stage, StudentPath.Stage.FOUNDATIONAL)
        foundational = issue_session(
            actor=self.student,
            session_type=Session.SessionType.FOUNDATIONAL,
            lesson=lesson,
        )
        self.assertEqual(foundational.items.count(), 3)
        with patch("apps.adaptive.services.decide") as decide_mock:
            self.complete_session(
                foundational,
                correct_per_skill={"S1": 0},
            )
        decide_mock.assert_not_called()
        self.finalize_feedback(foundational)

        decision = Decision.objects.get(session=foundational)
        self.path.refresh_from_db()
        self.assertEqual(decision.action, Decision.Action.PROGRESS)
        self.assertEqual(decision.reason_code, "foundational_fixed")
        self.assertEqual(self.path.current_lesson.lesson_order, 2)
        self.assertEqual(self.path.current_stage, StudentPath.Stage.LESSON)
        self.assertTrue(
            decision.target_skills.filter(
                skill__code="S1",
                target_kind=DecisionTargetSkill.TargetKind.FOLLOW_UP,
            ).exists()
        )

    def _create_failed_history(self, *, attempts=2):
        lesson = self.lesson(1)
        skill = self.skill("S1")
        question_set = self.question_set(
            QuestionSet.SetType.REGULAR,
            lesson=lesson,
        )
        rows = list(
            question_set.items.filter(question__skill=skill)
            .select_related("question")
            .prefetch_related("question__choices")
            .order_by("display_order")
        )
        for attempt in range(1, attempts + 1):
            now = timezone.now()
            session = Session.objects.create(
                student=self.student,
                session_type=Session.SessionType.REGULAR,
                lesson=lesson,
                status=Session.Status.COMPLETED,
                attempt_number=attempt + 10,
                submitted_at=now,
                completed_at=now,
            )
            for display_order, row in enumerate(rows, start=1):
                item = SessionItem.objects.create(
                    session=session,
                    question=row.question,
                    display_order=display_order,
                )
                Response.objects.create(
                    session_item=item,
                    selected_choice=next(
                        choice
                        for choice in row.question.choices.all()
                        if not choice.is_correct
                    ),
                )

    def test_branch_c_third_failure_forces_safety_cap_and_follow_up(self):
        self._create_failed_history(attempts=2)
        _lesson, third_attempt = self.start_lesson_one_regular()
        with patch(
            "apps.adaptive.services.decide",
            return_value=(
                Decision.Action.FOUNDATIONAL_EXERCISE,
                "q_learning_argmax",
            ),
        ) as decide_mock:
            self.complete_session(
                third_attempt,
                correct_per_skill=self.one_weak_skill_scores(third_attempt),
            )
        decide_mock.assert_called_once()

        decision = Decision.objects.get(session=third_attempt)
        self.assertEqual(decision.action, Decision.Action.PROGRESS)
        self.assertEqual(decision.reason_code, "safety_cap")
        self.assertTrue(
            decision.target_skills.filter(
                skill__code="S1",
                target_kind=DecisionTargetSkill.TargetKind.FOLLOW_UP,
            ).exists()
        )
