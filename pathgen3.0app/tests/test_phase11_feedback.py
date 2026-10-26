from contextlib import contextmanager
from unittest.mock import Mock, patch

from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext
from django.utils import timezone

from apps.adaptive.models import Decision, SkillMastery
from apps.feedback.models import SessionFeedback
from apps.feedback.prompts import MAX_PROMPT_CHARS, SYSTEM_INSTRUCTION, assemble_prompt
from apps.feedback.services import generate_fallback_draft
from apps.learning.models import Session, StudentPath
from apps.learning.services.finalization import finalize_pending_sessions
from tests.phase9_helpers import Phase9SeededTestCase


VALID_RESPONSE = (
    "Nice work identifying integer relationships. Review the lesson examples "
    "and explain your reasoning carefully."
)
RETRIEVED_CHUNKS = [
    {
        "chunk_id": "L1-B01",
        "text": "Integers can be positive, negative, or zero.",
    }
]


class FakeOpenAIClient:
    def embed(self, text):
        return [1.0] + ([0.0] * 1535), 20


class Phase11FeedbackTests(Phase9SeededTestCase):
    def _pending_regular(self, *, action=Decision.Action.PROGRESS, failing=()):
        session = self.exercise_session(Session.SessionType.REGULAR)
        with patch(
            "apps.adaptive.services.decide",
            return_value=(action, "phase11_test"),
        ):
            self.submit_all(session, failing_skill_codes=set(failing))
        session.refresh_from_db()
        self.assertEqual(session.status, Session.Status.SUBMITTED)
        self.assertEqual(session.adaptive_decision.action, action)
        return session

    def _provider_context(self, *, response=VALID_RESPONSE, chunks=None, error=None):
        groq_instance = Mock()
        groq_instance.model = "gpt-oss-120b"
        if error is None:
            groq_instance.generate.return_value = response
        else:
            groq_instance.generate.side_effect = error
        groq_class = Mock(return_value=groq_instance)
        stack = self.enterContext(
            patch(
                "apps.feedback.services.get_embedding_client",
                return_value=FakeOpenAIClient(),
            )
        )
        self.enterContext(
            patch(
                "apps.feedback.services.retrieve",
                return_value=RETRIEVED_CHUNKS if chunks is None else chunks,
            )
        )
        self.enterContext(
            patch("apps.feedback.services.GroqFeedbackClient", groq_class)
        )
        return groq_class, groq_instance, stack

    def test_regular_valid_response_is_generated(self):
        session = self._pending_regular()
        self._provider_context()
        self.assertEqual(finalize_pending_sessions(), 1)
        feedback = SessionFeedback.objects.get(session=session)
        self.assertEqual(feedback.generation_status, "generated")
        self.assertEqual(feedback.model_name, "gpt-oss-120b")
        self.assertEqual(feedback.feedback_text, VALID_RESPONSE)

    def test_groq_timeout_uses_fallback(self):
        session = self._pending_regular()
        self._provider_context(error=TimeoutError("provider timeout"))
        self.assertEqual(finalize_pending_sessions(), 1)
        feedback = SessionFeedback.objects.get(session=session)
        self.assertEqual(feedback.generation_status, "fallback")
        self.assertIsNone(feedback.model_name)

    def test_more_than_180_words_uses_fallback(self):
        session = self._pending_regular()
        self._provider_context(response="word " * 181)
        finalize_pending_sessions()
        self.assertEqual(
            SessionFeedback.objects.get(session=session).generation_status,
            "fallback",
        )

    def test_credential_phrase_uses_fallback(self):
        session = self._pending_regular()
        self._provider_context(response="Your API key is safe. Keep practicing.")
        finalize_pending_sessions()
        self.assertEqual(
            SessionFeedback.objects.get(session=session).generation_status,
            "fallback",
        )

    def test_prepost_answer_key_uses_fallback(self):
        session = self._pending_regular()
        self._provider_context(
            response="Remember the representation Four positive counters."
        )
        finalize_pending_sessions()
        self.assertEqual(
            SessionFeedback.objects.get(session=session).generation_status,
            "fallback",
        )

    def test_output_contradicting_action_uses_fallback(self):
        session = self._pending_regular(
            action=Decision.Action.FOUNDATIONAL_EXERCISE,
            failing={"S1"},
        )
        self._provider_context(response="Good work. Move on to the next lesson.")
        finalize_pending_sessions()
        self.assertEqual(
            SessionFeedback.objects.get(session=session).generation_status,
            "fallback",
        )

    def test_empty_retrieval_skips_groq_and_uses_fallback(self):
        session = self._pending_regular()
        groq_class, _, _ = self._provider_context(chunks=[])
        finalize_pending_sessions()
        groq_class.assert_not_called()
        self.assertEqual(
            SessionFeedback.objects.get(session=session).generation_status,
            "fallback",
        )

    def test_prompt_bounds_truncate_chunks_before_evidence(self):
        evidence = {
            "lesson_code": "L1",
            "weak_skills": ["S1"],
            "correct_count": 5,
            "total_count": 6,
            "hint_used": False,
        }
        chunks = [{"chunk_id": "L1-B01", "text": "x" * 15_000 + "CHUNK_TAIL"}]
        prompt = assemble_prompt(evidence, chunks, Decision.Action.PROGRESS)
        self.assertLessEqual(len(prompt), MAX_PROMPT_CHARS)
        self.assertTrue(prompt.startswith(SYSTEM_INSTRUCTION))
        self.assertIn('"weak_skills":["S1"]', prompt)
        self.assertNotIn("CHUNK_TAIL", prompt)

    def test_prepost_session_creates_no_feedback(self):
        session = Session.objects.create(
            student=self.student,
            session_type=Session.SessionType.PRETEST,
            status=Session.Status.SUBMITTED,
            attempt_number=1,
            submitted_at=timezone.now(),
        )
        openai_client = self.enterContext(
            patch("apps.feedback.services.get_embedding_client")
        )
        groq_client = self.enterContext(
            patch("apps.feedback.services.GroqFeedbackClient")
        )
        self.assertEqual(finalize_pending_sessions(), 1)
        session.refresh_from_db()
        self.assertEqual(session.status, Session.Status.COMPLETED)
        self.assertFalse(SessionFeedback.objects.filter(session=session).exists())
        openai_client.assert_not_called()
        groq_client.assert_not_called()

    def test_duplicate_finalization_creates_one_feedback_row(self):
        session = self._pending_regular()
        self._provider_context()
        with CaptureQueriesContext(connection) as queries:
            self.assertEqual(finalize_pending_sessions(), 1)
        self.assertEqual(finalize_pending_sessions(), 0)
        self.assertEqual(SessionFeedback.objects.filter(session=session).count(), 1)
        self.assertTrue(
            any(
                "ON CONFLICT DO NOTHING" in query["sql"]
                for query in queries.captured_queries
            )
        )

    def test_fallback_is_deterministic(self):
        session = self._pending_regular(failing={"S1"})
        first = generate_fallback_draft(session)
        second = generate_fallback_draft(session)
        self.assertEqual(first, second)

    def test_finalizer_creates_feedback_for_all_pending_eligible_types(self):
        sessions = []
        for session_type in (
            Session.SessionType.REGULAR,
            Session.SessionType.ADDITIONAL,
            Session.SessionType.FOUNDATIONAL,
            Session.SessionType.ACTIVITY,
        ):
            session = Session.objects.create(
                student=self.student,
                session_type=session_type,
                lesson=(
                    None
                    if session_type == Session.SessionType.ACTIVITY
                    else self.lesson(1)
                ),
                status=Session.Status.SUBMITTED,
                attempt_number=1,
                submitted_at=timezone.now(),
            )
            Decision.objects.create(
                session=session,
                action=Decision.Action.PROGRESS,
                reason_code="phase11_test",
                policy_version="Q-LEARNING-V1",
                input_snapshot_json={},
            )
            sessions.append(session)
        self._provider_context()
        self.assertEqual(finalize_pending_sessions(), 4)
        self.assertEqual(
            SessionFeedback.objects.filter(session__in=sessions).count(),
            4,
        )
        self.assertFalse(
            Session.objects.filter(pk__in=[row.pk for row in sessions])
            .exclude(status=Session.Status.COMPLETED)
            .exists()
        )

    def test_finalizer_is_idempotent(self):
        session = self._pending_regular()
        self._provider_context()
        first = finalize_pending_sessions()
        second = finalize_pending_sessions()
        self.assertEqual((first, second), (1, 0))
        self.assertEqual(SessionFeedback.objects.filter(session=session).count(), 1)

    def test_provider_calls_happen_before_application_atomic_block(self):
        self._pending_regular()
        real_atomic = transaction.atomic
        inside_finalization_atomic = {"value": False}

        @contextmanager
        def monitored_atomic(*args, **kwargs):
            with real_atomic(*args, **kwargs):
                inside_finalization_atomic["value"] = True
                try:
                    yield
                finally:
                    inside_finalization_atomic["value"] = False

        class TransactionAwareOpenAI:
            def embed(inner_self, text):
                self.assertFalse(inside_finalization_atomic["value"])
                return [1.0] + ([0.0] * 1535), 20

        class TransactionAwareGroq:
            model = "gpt-oss-120b"

            def generate(inner_self, prompt):
                self.assertFalse(inside_finalization_atomic["value"])
                return VALID_RESPONSE

        with patch(
            "apps.learning.services.finalization.transaction.atomic",
            monitored_atomic,
        ), patch(
            "apps.feedback.services.get_embedding_client",
            return_value=TransactionAwareOpenAI(),
        ), patch(
            "apps.feedback.services.retrieve",
            return_value=RETRIEVED_CHUNKS,
        ), patch(
            "apps.feedback.services.GroqFeedbackClient",
            return_value=TransactionAwareGroq(),
        ):
            self.assertEqual(finalize_pending_sessions(), 1)

    def test_rag_does_not_update_mastery_decision_or_path(self):
        session = self._pending_regular(failing={"S1"})
        mastery_before = list(
            SkillMastery.objects.filter(student=self.student)
            .order_by("skill_id")
            .values("skill_id", "p_known", "evidence_count", "updated_at")
        )
        decision_before = list(
            Decision.objects.filter(session=session).values(
                "id",
                "action",
                "reason_code",
                "policy_version",
                "input_snapshot_json",
                "created_at",
            )
        )
        self.path.refresh_from_db()
        path_before = (
            self.path.status,
            self.path.current_stage,
            self.path.current_lesson_id,
            self.path.updated_at,
        )
        self._provider_context()
        finalize_pending_sessions()
        self.assertEqual(
            list(
                SkillMastery.objects.filter(student=self.student)
                .order_by("skill_id")
                .values("skill_id", "p_known", "evidence_count", "updated_at")
            ),
            mastery_before,
        )
        self.assertEqual(
            list(
                Decision.objects.filter(session=session).values(
                    "id",
                    "action",
                    "reason_code",
                    "policy_version",
                    "input_snapshot_json",
                    "created_at",
                )
            ),
            decision_before,
        )
        self.path.refresh_from_db()
        self.assertEqual(
            (
                self.path.status,
                self.path.current_stage,
                self.path.current_lesson_id,
                self.path.updated_at,
            ),
            path_before,
        )
