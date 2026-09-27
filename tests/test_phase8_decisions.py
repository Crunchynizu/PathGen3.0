from unittest.mock import patch

from django.utils import timezone

from apps.adaptive.models import Decision, DecisionTargetSkill
from apps.curriculum.models import QuestionSet
from apps.learning.models import Response, Session, SessionItem, StudentPath
from apps.learning.services.responses import submit_response
from tests.phase6_helpers import Phase6SeededTestCase


class DecisionPersistenceTests(Phase6SeededTestCase):
    def _exercise_session(self, session_type, *, skill_code=None):
        lesson = self.lesson(1)
        set_type = {
            Session.SessionType.REGULAR: QuestionSet.SetType.REGULAR,
            Session.SessionType.ADDITIONAL: QuestionSet.SetType.ADDITIONAL,
            Session.SessionType.FOUNDATIONAL: QuestionSet.SetType.FOUNDATIONAL,
        }[session_type]
        skill = self.skill(skill_code) if skill_code else None
        self.set_path(
            status=StudentPath.Status.LEARNING,
            stage=session_type,
            lesson=lesson,
        )
        return self.make_session_from_set(
            session_type=session_type,
            question_set=self.question_set(
                set_type,
                lesson=lesson if skill is None else None,
                skill=skill,
            ),
            lesson=lesson,
        )

    def _submit_all(self, session, *, failing_skill_codes=()):
        result = None
        for item in session.items.select_related("question").order_by("display_order"):
            choices = item.question.choices.order_by("display_order")
            if item.question.skill.code in failing_skill_codes:
                choice = choices.filter(is_correct=False).first()
            else:
                choice = choices.get(is_correct=True)
            result = submit_response(
                actor=self.student,
                session_id=session.pk,
                session_item_id=item.pk,
                selected_choice_id=choice.pk,
            )
        return result

    def _one_item_session(self, session_type, question_set):
        return self.make_session_from_set(
            session_type=session_type,
            question_set=question_set,
            limit=1,
        )

    def _add_failed_history(self, *, skill, attempts=2):
        question_set = self.question_set(
            QuestionSet.SetType.REGULAR,
            lesson=self.lesson(1),
        )
        questions = list(
            question_set.items.filter(question__skill=skill)
            .select_related("question")
            .order_by("display_order")
        )
        self.assertEqual(len(questions), 3)
        for attempt in range(1, attempts + 1):
            session = Session.objects.create(
                student=self.student,
                session_type=Session.SessionType.REGULAR,
                lesson=self.lesson(1),
                status=Session.Status.COMPLETED,
                attempt_number=attempt + 10,
                submitted_at=timezone.now(),
                completed_at=timezone.now(),
            )
            for display_order, row in enumerate(questions, start=1):
                item = SessionItem.objects.create(
                    session=session,
                    question=row.question,
                    display_order=display_order,
                )
                Response.objects.create(
                    session_item=item,
                    selected_choice=row.question.choices.filter(is_correct=False).first(),
                )

    def test_regular_finalization_creates_one_decision(self):
        session = self._exercise_session(Session.SessionType.REGULAR)
        self._submit_all(session)
        decision = Decision.objects.get(session=session)
        self.assertEqual(decision.reason_code, "q_learning_argmax")

    def test_snapshot_contains_state_q_values_and_chosen_action(self):
        session = self._exercise_session(Session.SessionType.REGULAR)
        with patch(
            "apps.adaptive.services.decide",
            return_value=("progress", "q_learning_argmax"),
        ):
            self._submit_all(session)
        snapshot = Decision.objects.get(session=session).input_snapshot_json
        self.assertEqual(snapshot["chosen_action"], "progress")
        self.assertTrue(snapshot["state"].startswith("("))
        self.assertEqual(set(snapshot["q_values"]), {
            "progress",
            "additional_exercise",
            "foundational_exercise",
        })
        self.assertEqual(snapshot["policy_version"], "Q-LEARNING-V1")

    def test_remediation_creates_next_exercise_target_for_failed_skill(self):
        session = self._exercise_session(Session.SessionType.REGULAR)
        with patch(
            "apps.adaptive.services.decide",
            return_value=("foundational_exercise", "q_learning_argmax"),
        ):
            self._submit_all(session, failing_skill_codes={"S1"})
        targets = DecisionTargetSkill.objects.filter(decision__session=session)
        self.assertEqual(targets.count(), 1)
        self.assertEqual(targets.get().skill.code, "S1")
        self.assertEqual(targets.get().target_kind, "next_exercise")

    def test_foundational_finalization_is_fixed_progress_with_follow_up(self):
        session = self._exercise_session(
            Session.SessionType.FOUNDATIONAL,
            skill_code="S1",
        )
        with patch("apps.adaptive.services.decide") as decide_mock:
            self._submit_all(session, failing_skill_codes={"S1"})
        decide_mock.assert_not_called()
        decision = Decision.objects.get(session=session)
        self.assertEqual(decision.action, "progress")
        self.assertEqual(decision.reason_code, "foundational_fixed")
        self.assertTrue(
            decision.target_skills.filter(
                skill__code="S1",
                target_kind="follow_up",
            ).exists()
        )

    def test_activity_finalization_is_fixed_progress(self):
        self.set_path(
            status=StudentPath.Status.ACTIVITY_READY,
            stage=StudentPath.Stage.ACTIVITY,
            lesson=self.lesson(3),
        )
        session = self.make_session_from_set(
            session_type=Session.SessionType.ACTIVITY,
            question_set=self.question_set(QuestionSet.SetType.ACTIVITY),
        )
        with patch("apps.adaptive.services.decide") as decide_mock:
            self._submit_all(session)
        decide_mock.assert_not_called()
        decision = Decision.objects.get(session=session)
        self.assertEqual(decision.action, "progress")
        self.assertEqual(decision.reason_code, "activity_fixed")
        self.path.refresh_from_db()
        self.assertEqual(self.path.status, StudentPath.Status.POSTTEST_READY)

    def test_safety_cap_forces_progress_on_third_failure(self):
        skill = self.skill("S1")
        self._add_failed_history(skill=skill)
        session = self._exercise_session(Session.SessionType.REGULAR)
        with patch(
            "apps.adaptive.services.decide",
            return_value=("foundational_exercise", "q_learning_argmax"),
        ):
            self._submit_all(session, failing_skill_codes={"S1"})
        decision = Decision.objects.get(session=session)
        self.assertEqual(decision.action, "progress")
        self.assertEqual(decision.reason_code, "safety_cap")
        self.assertTrue(
            decision.target_skills.filter(
                skill=skill,
                target_kind="follow_up",
            ).exists()
        )

    def test_duplicate_final_submission_does_not_create_second_decision(self):
        session = self._exercise_session(Session.SessionType.REGULAR)
        with patch(
            "apps.adaptive.services.decide",
            return_value=("progress", "q_learning_argmax"),
        ):
            result = self._submit_all(session)
            submit_response(
                actor=self.student,
                session_id=session.pk,
                session_item_id=result.response.session_item_id,
                selected_choice_id=result.response.selected_choice_id,
            )
        self.assertEqual(Decision.objects.filter(session=session).count(), 1)

    def test_posttest_creates_zero_decisions(self):
        self.setting.posttest_access_enabled = True
        self.setting.save(update_fields=["posttest_access_enabled"])
        self.set_path(
            status=StudentPath.Status.POSTTEST_READY,
            stage=StudentPath.Stage.POSTTEST,
            lesson=self.lesson(3),
        )
        session = self._one_item_session(
            Session.SessionType.POSTTEST,
            self.question_set(QuestionSet.SetType.PREPOST),
        )
        with patch("apps.adaptive.services.decide") as decide_mock:
            self._submit_all(session)
        decide_mock.assert_not_called()
        self.assertFalse(Decision.objects.filter(session=session).exists())

    def test_pretest_creates_zero_decisions(self):
        session = self._one_item_session(
            Session.SessionType.PRETEST,
            self.question_set(QuestionSet.SetType.PREPOST),
        )
        with patch("apps.adaptive.services.decide") as decide_mock:
            self._submit_all(session)
        decide_mock.assert_not_called()
        self.assertFalse(Decision.objects.filter(session=session).exists())
