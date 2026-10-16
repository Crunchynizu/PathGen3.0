from decimal import Decimal, ROUND_HALF_EVEN

from apps.adaptive.bkt import update_mastery
from apps.adaptive.models import Decision, MasteryEvent, SkillMastery
from apps.feedback.models import SessionFeedback
from apps.feedback.services import generate_fallback_draft
from apps.learning.models import Session
from tests.integration._helpers import IntegrationSeededTestCase


SIX_PLACES = Decimal("0.000001")
REPLAY_TOLERANCE = Decimal("0.000000000001")


def persisted_probability(value):
    return Decimal(str(value)).quantize(SIX_PLACES, rounding=ROUND_HALF_EVEN)


class ProvenanceReplayAcceptanceTests(IntegrationSeededTestCase):
    def test_completed_student_replays_bkt_decisions_and_feedback(self):
        self.complete_full_path(pretest_correct=0, posttest_correct=30)

        replayed = {}
        events = MasteryEvent.objects.filter(
            mastery__student=self.student
        ).select_related(
            "mastery__skill",
            "response__selected_choice",
            "response__session_item__session",
        ).order_by("created_at", "pk")
        self.assertTrue(events.exists())
        for event in events:
            skill = event.mastery.skill
            session_type = event.response.session_item.session.session_type
            p_before = replayed.get(skill.pk, persisted_probability(skill.p_l0))
            self.assertLessEqual(
                abs(Decimal(event.p_before) - p_before),
                REPLAY_TOLERANCE,
            )
            result = update_mastery(
                p_before,
                event.response.selected_choice.is_correct,
                skill.p_t,
                skill.p_g,
                skill.p_s,
                apply_learning_transition=session_type != Session.SessionType.PRETEST,
                posterior_only=session_type == Session.SessionType.PRETEST,
            )
            expected_observation = persisted_probability(
                result.p_after_observation
            )
            expected_after = persisted_probability(result.p_after_learning)
            self.assertLessEqual(
                abs(
                    Decimal(event.p_after_observation)
                    - expected_observation
                ),
                REPLAY_TOLERANCE,
            )
            self.assertLessEqual(
                abs(Decimal(event.p_after_learning) - expected_after),
                REPLAY_TOLERANCE,
            )
            self.assertEqual(
                event.learning_transition_applied,
                session_type != Session.SessionType.PRETEST,
            )
            replayed[skill.pk] = expected_after

        for mastery in SkillMastery.objects.filter(student=self.student):
            self.assertLessEqual(
                abs(Decimal(mastery.p_known) - replayed[mastery.skill_id]),
                REPLAY_TOLERANCE,
            )

        decisions = Decision.objects.filter(
            session__student=self.student
        ).order_by("created_at", "pk")
        self.assertTrue(decisions.exists())
        for decision in decisions:
            snapshot = decision.input_snapshot_json
            available = snapshot["available_actions"]
            q_values = snapshot["q_values"]
            if q_values:
                candidates = {
                    action: q_values[action]
                    for action in available
                    if action in q_values
                }
                replayed_action = max(
                    sorted(candidates),
                    key=candidates.__getitem__,
                )
            else:
                self.assertEqual(len(available), 1)
                replayed_action = available[0]
            self.assertEqual(snapshot["chosen_action"], replayed_action)
            self.assertEqual(decision.action, replayed_action)
            self.assertEqual(decision.policy_version, "Q-LEARNING-V1")
            self.assertEqual(snapshot["policy_version"], "Q-LEARNING-V1")

        feedback_rows = SessionFeedback.objects.filter(
            session__student=self.student
        ).select_related("session")
        self.assertTrue(feedback_rows.exists())
        for feedback in feedback_rows:
            self.assertIn(
                feedback.generation_status,
                {
                    SessionFeedback.GenerationStatus.GENERATED,
                    SessionFeedback.GenerationStatus.FALLBACK,
                },
            )
            if (
                feedback.generation_status
                == SessionFeedback.GenerationStatus.FALLBACK
            ):
                expected = generate_fallback_draft(feedback.session)
                self.assertEqual(feedback.feedback_text, expected.feedback_text)
                self.assertIsNone(feedback.model_name)
            else:
                self.assertEqual(feedback.model_name, "gpt-oss-120b")
