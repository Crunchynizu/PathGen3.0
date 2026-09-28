from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.adaptive.models import Decision, DecisionTargetSkill, MasteryEvent
from apps.feedback.models import SessionFeedback
from apps.feedback.services import generate_fallback_draft
from apps.learning.models import Session, StudentPath
from apps.learning.services.finalization import finalize_pending_sessions
from apps.learning.services.paths import open_regular_stage
from apps.learning.services.responses import submit_response
from apps.learning.services.sessions import issue_session
from tests.phase9_helpers import Phase9SeededTestCase


class OrchestratorTests(Phase9SeededTestCase):
    def _complete_issued(self, session):
        return self.submit_all(session)

    def _complete_regular_lesson(self, lesson):
        open_regular_stage(actor=self.student, lesson=lesson)
        session = issue_session(
            actor=self.student,
            session_type=Session.SessionType.REGULAR,
            lesson=lesson,
        )
        self._complete_issued(session)
        self.assertEqual(
            finalize_pending_sessions(feedback_generator=generate_fallback_draft),
            1,
        )
        return session

    def test_full_pretest_lessons_activity_posttest_flow_completes(self):
        pretest = issue_session(
            actor=self.student,
            session_type=Session.SessionType.PRETEST,
        )
        self._complete_issued(pretest)

        regular_sessions = [
            self._complete_regular_lesson(self.lesson(order))
            for order in (1, 2, 3)
        ]

        activity = issue_session(
            actor=self.student,
            session_type=Session.SessionType.ACTIVITY,
        )
        self._complete_issued(activity)
        self.assertEqual(
            finalize_pending_sessions(feedback_generator=generate_fallback_draft),
            1,
        )

        self.setting.posttest_access_enabled = True
        self.setting.save(update_fields=["posttest_access_enabled"])
        posttest = issue_session(
            actor=self.student,
            session_type=Session.SessionType.POSTTEST,
        )
        self._complete_issued(posttest)

        self.path.refresh_from_db()
        posttest.refresh_from_db()
        self.assertEqual(self.path.status, StudentPath.Status.COMPLETED)
        self.assertEqual(posttest.status, Session.Status.COMPLETED)
        self.assertEqual(Decision.objects.count(), 4)
        self.assertEqual(SessionFeedback.objects.count(), 4)
        self.assertEqual(
            Decision.objects.filter(session__in=[pretest, posttest]).count(),
            0,
        )
        self.assertEqual(
            MasteryEvent.objects.filter(
                response__session_item__session=posttest
            ).count(),
            0,
        )
        self.assertEqual(len(regular_sessions), 3)

    def test_regular_passes_progress_to_next_lesson(self):
        session = self.exercise_session(Session.SessionType.REGULAR)
        self.submit_all(session)
        decision = Decision.objects.get(session=session)
        self.path.refresh_from_db()
        self.assertEqual(decision.action, Decision.Action.PROGRESS)
        self.assertEqual(self.path.current_lesson.lesson_order, 2)
        self.assertEqual(self.path.current_stage, StudentPath.Stage.LESSON)

    def test_regular_failure_routes_to_remediation(self):
        session = self.exercise_session(Session.SessionType.REGULAR)
        self.submit_all(session, failing_skill_codes={"S1"})
        decision = Decision.objects.get(session=session)
        self.path.refresh_from_db()
        self.assertIn(
            decision.action,
            {
                Decision.Action.ADDITIONAL_EXERCISE,
                Decision.Action.FOUNDATIONAL_EXERCISE,
            },
        )
        self.assertEqual(self.path.current_stage, decision.action.removesuffix("_exercise"))

    def test_additional_completion_decides_again(self):
        session = self.exercise_session(Session.SessionType.ADDITIONAL)
        self.submit_all(session)
        decision = Decision.objects.get(session=session)
        self.path.refresh_from_db()
        self.assertEqual(decision.action, Decision.Action.PROGRESS)
        self.assertEqual(self.path.current_lesson.lesson_order, 2)

    def test_foundational_completion_progresses_with_follow_up(self):
        session = self.exercise_session(
            Session.SessionType.FOUNDATIONAL,
            skill_code="S1",
        )
        self.submit_all(session, failing_skill_codes={"S1"})
        decision = Decision.objects.get(session=session)
        self.assertEqual(decision.action, Decision.Action.PROGRESS)
        self.assertEqual(decision.reason_code, "foundational_fixed")
        self.assertTrue(
            DecisionTargetSkill.objects.filter(
                decision=decision,
                skill__code="S1",
                target_kind=DecisionTargetSkill.TargetKind.FOLLOW_UP,
            ).exists()
        )

    def test_posttest_creates_no_adaptive_evidence_or_feedback(self):
        self.setting.posttest_access_enabled = True
        self.setting.save(update_fields=["posttest_access_enabled"])
        self.set_path(
            status=StudentPath.Status.POSTTEST_READY,
            stage=StudentPath.Stage.POSTTEST,
            lesson=self.lesson(3),
        )
        session = self.make_session_from_set(
            session_type=Session.SessionType.POSTTEST,
            question_set=self.question_set("prepost"),
            limit=1,
        )
        self.submit_all(session)
        self.assertFalse(Decision.objects.filter(session=session).exists())
        self.assertFalse(SessionFeedback.objects.filter(session=session).exists())
        self.assertFalse(
            MasteryEvent.objects.filter(
                response__session_item__session=session
            ).exists()
        )

    def test_pretest_creates_zero_decisions(self):
        session = self.make_session_from_set(
            session_type=Session.SessionType.PRETEST,
            question_set=self.question_set("prepost"),
            limit=1,
        )
        self.submit_all(session)
        self.assertFalse(Decision.objects.filter(session=session).exists())

    def test_duplicate_final_post_creates_one_decision(self):
        session = self.exercise_session(Session.SessionType.REGULAR)
        result = self.submit_all(session)
        submit_response(
            actor=self.student,
            session_id=session.pk,
            session_item_id=result.response.session_item_id,
            selected_choice_id=result.response.selected_choice_id,
        )
        self.assertEqual(Decision.objects.filter(session=session).count(), 1)

    def test_submission_queries_lock_path_before_session_before_mastery(self):
        session = self.exercise_session(Session.SessionType.REGULAR)
        item = session.items.select_related("question").order_by("display_order").first()
        with CaptureQueriesContext(connection) as queries:
            self.submit_item(session, item)
        sql = [query["sql"] for query in queries.captured_queries]
        path_lock = next(
            index
            for index, query in enumerate(sql)
            if "learning_student_path" in query and "FOR UPDATE" in query
        )
        session_lock = next(
            index
            for index, query in enumerate(sql)
            if "learning_session" in query
            and "learning_session_item" not in query
            and "FOR UPDATE" in query
        )
        mastery_lock = next(
            index
            for index, query in enumerate(sql)
            if "adaptive_skill_mastery" in query and "FOR UPDATE" in query
        )
        self.assertLess(path_lock, session_lock)
        self.assertLess(session_lock, mastery_lock)

    def test_deterministic_commit_leaves_feedback_eligible_session_submitted(self):
        session = self.exercise_session(Session.SessionType.REGULAR)
        self.submit_all(session)
        session.refresh_from_db()
        self.assertEqual(session.status, Session.Status.SUBMITTED)
        self.assertIsNotNone(session.submitted_at)
        self.assertIsNone(session.completed_at)
        self.assertFalse(SessionFeedback.objects.filter(session=session).exists())

    def test_finalize_pending_sessions_writes_fallback_and_completes(self):
        session = self.exercise_session(Session.SessionType.REGULAR)
        self.submit_all(session)
        self.assertEqual(
            finalize_pending_sessions(feedback_generator=generate_fallback_draft),
            1,
        )
        session.refresh_from_db()
        feedback = SessionFeedback.objects.get(session=session)
        self.assertEqual(session.status, Session.Status.COMPLETED)
        self.assertIsNotNone(session.completed_at)
        self.assertEqual(feedback.generation_status, "fallback")
        self.assertIsNone(feedback.model_name)

    def test_finalize_pending_sessions_is_idempotent(self):
        session = self.exercise_session(Session.SessionType.REGULAR)
        self.submit_all(session)
        self.assertEqual(
            finalize_pending_sessions(feedback_generator=generate_fallback_draft),
            1,
        )
        self.assertEqual(
            finalize_pending_sessions(feedback_generator=generate_fallback_draft),
            0,
        )
        self.assertEqual(SessionFeedback.objects.filter(session=session).count(), 1)
