from apps.adaptive.models import MasteryEvent, SkillMastery
from apps.learning.models import Response, Session, StudentPath
from tests.integration._helpers import IntegrationSeededTestCase


class PosttestNoBKTAcceptanceTests(IntegrationSeededTestCase):
    def test_full_path_posttest_creates_no_events_or_mastery_change(self):
        sessions = self.complete_through_activity(pretest_correct=0)
        self.assertEqual(self.path.status, StudentPath.Status.POSTTEST_READY)

        pretest_events = MasteryEvent.objects.filter(
            response__session_item__session=sessions["pretest"]
        )
        self.assertEqual(pretest_events.count(), 30)
        self.assertFalse(
            pretest_events.filter(learning_transition_applied=True).exists()
        )

        eligible_response_count = Response.objects.filter(
            session_item__session__student=self.student
        ).exclude(
            session_item__session__session_type=Session.SessionType.POSTTEST
        ).count()
        events_before = MasteryEvent.objects.filter(
            mastery__student=self.student
        ).count()
        self.assertEqual(events_before, eligible_response_count)
        mastery_before = dict(
            SkillMastery.objects.filter(student=self.student).values_list(
                "skill_id",
                "p_known",
            )
        )

        posttest = self.complete_posttest(correct_total=30)
        self.assertEqual(self.path.status, StudentPath.Status.COMPLETED)
        self.assertFalse(
            MasteryEvent.objects.filter(
                response__session_item__session=posttest
            ).exists()
        )
        self.assertEqual(
            MasteryEvent.objects.filter(mastery__student=self.student).count(),
            events_before,
        )
        mastery_after = dict(
            SkillMastery.objects.filter(student=self.student).values_list(
                "skill_id",
                "p_known",
            )
        )
        self.assertEqual(mastery_after, mastery_before)
