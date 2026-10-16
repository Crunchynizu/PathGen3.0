from apps.accounts.models import User
from apps.core.metrics import matched_gain, matched_prepost_sample
from apps.learning.models import Session
from tests.factories import make_user
from tests.integration._helpers import (
    IntegrationSeededTestCase,
    create_completed_assessment,
)


class MatchedPrePostAcceptanceTests(IntegrationSeededTestCase):
    def test_only_students_with_both_completed_assessments_are_matched(self):
        student_one = make_user(User.Role.STUDENT)
        student_two = make_user(User.Role.STUDENT)
        unmatched_student = make_user(User.Role.STUDENT)

        one_pre = create_completed_assessment(
            student=student_one,
            session_type=Session.SessionType.PRETEST,
            correct_total=10,
        )
        one_post = create_completed_assessment(
            student=student_one,
            session_type=Session.SessionType.POSTTEST,
            correct_total=20,
        )
        two_pre = create_completed_assessment(
            student=student_two,
            session_type=Session.SessionType.PRETEST,
            correct_total=15,
        )
        two_post = create_completed_assessment(
            student=student_two,
            session_type=Session.SessionType.POSTTEST,
            correct_total=30,
        )
        create_completed_assessment(
            student=unmatched_student,
            session_type=Session.SessionType.PRETEST,
            correct_total=25,
        )

        self.assertEqual(self.score(one_post) - self.score(one_pre), 10)
        self.assertEqual(self.score(two_post) - self.score(two_pre), 15)

        cohort = User.objects.filter(
            pk__in=[student_one.pk, student_two.pk, unmatched_student.pk]
        )
        sample = matched_prepost_sample(cohort, cohort="Acceptance cohort")
        gain = matched_gain(cohort, cohort="Acceptance cohort")

        self.assertEqual(sample["value"], 2)
        self.assertEqual(sample["n"], 2)
        self.assertEqual(gain["n"], 2)
        expected_gain = round(
            (((20 - 10) / 30 * 100) + ((30 - 15) / 30 * 100)) / 2,
            1,
        )
        self.assertEqual(gain["value"], expected_gain)
        self.assertEqual(gain["cohort"], "Acceptance cohort")
        self.assertTrue(gain["definition"])
        self.assertEqual(gain["version"], "METRICS-V1")
        self.assertEqual(sample["cohort"], "Acceptance cohort")
        self.assertTrue(sample["definition"])
