from django.urls import reverse

from apps.accounts.models import User
from apps.adaptive.models import Decision, MasteryEvent
from apps.classrooms.models import StudentMembership
from apps.core.metrics import matched_gain
from apps.feedback.models import SessionFeedback
from apps.learning.models import Session, StudentPath
from tests.integration._helpers import IntegrationSeededTestCase


PASSWORD = "Phase14!FullPathPassword"


class FullStudentPathAcceptanceTests(IntegrationSeededTestCase):
    def test_class_free_student_completes_the_entire_learning_path(self):
        self.student.set_password(PASSWORD)
        self.student.save(update_fields=["password", "updated_at"])
        login = self.client.post(
            reverse("account:login"),
            {"username": self.student.username, "password": PASSWORD},
        )
        self.assertRedirects(login, reverse("account:student_dashboard"))
        self.assertFalse(
            StudentMembership.objects.filter(student=self.student).exists()
        )

        pretest = self.complete_pretest(correct_total=0)
        self.assertEqual(pretest.items.count(), 30)
        self.assertEqual(self.path.status, StudentPath.Status.LEARNING)
        self.assertEqual(self.path.current_lesson.lesson_order, 1)
        self.assertEqual(self.path.current_stage, StudentPath.Stage.LESSON)

        regular_sessions = []
        lessons = self.lessons()
        self.assertEqual([lesson.display_label for lesson in lessons],
                         ["Lesson 1.1", "Lesson 1.2", "Lesson 2.1", "Lesson 2.2", "Lesson 2.3", "Lesson 3.1", "Lesson 3.2"])
        for lesson in lessons:
            session = self.complete_regular_lesson(lesson)
            regular_sessions.append(session)
            self.assertEqual(session.items.count(), 6)
            if lesson != lessons[-1]:
                self.assertEqual(self.path.status, StudentPath.Status.LEARNING)
                self.assertEqual(
                    self.path.current_lesson.lesson_order,
                    lesson.lesson_order + 1,
                )
                self.assertEqual(self.path.current_stage, StudentPath.Stage.LESSON)
            else:
                self.assertEqual(
                    self.path.status,
                    StudentPath.Status.ACTIVITY_READY,
                )
                self.assertEqual(
                    self.path.current_stage,
                    StudentPath.Stage.ACTIVITY,
                )

        activity = self.complete_activity(correct_total=10)
        self.assertEqual(activity.items.count(), 10)
        self.assertEqual(self.path.status, StudentPath.Status.POSTTEST_READY)
        self.assertEqual(self.path.current_stage, StudentPath.Stage.POSTTEST)

        posttest = self.complete_posttest(correct_total=30)
        self.assertEqual(posttest.items.count(), 30)
        self.assertEqual(self.path.status, StudentPath.Status.COMPLETED)
        self.assertEqual(self.path.current_stage, StudentPath.Stage.POSTTEST)

        eligible_sessions = [*regular_sessions, activity]
        for session in eligible_sessions:
            self.assertEqual(Decision.objects.filter(session=session).count(), 1)
            self.assertEqual(
                SessionFeedback.objects.filter(session=session).count(),
                1,
            )
        self.assertEqual(Decision.objects.count(), len(eligible_sessions))
        self.assertEqual(
            SessionFeedback.objects.count(),
            len(eligible_sessions),
        )

        for diagnostic in (pretest, posttest):
            self.assertFalse(Decision.objects.filter(session=diagnostic).exists())
            self.assertFalse(
                SessionFeedback.objects.filter(session=diagnostic).exists()
            )
        pretest_events = MasteryEvent.objects.filter(
            response__session_item__session=pretest
        )
        self.assertEqual(pretest_events.count(), 30)
        self.assertFalse(
            pretest_events.filter(learning_transition_applied=True).exists()
        )
        self.assertFalse(
            MasteryEvent.objects.filter(
                response__session_item__session=posttest
            ).exists()
        )

        pretest_score = self.score(pretest)
        posttest_score = self.score(posttest)
        self.assertEqual(posttest_score - pretest_score, 30)
        metric = matched_gain(
            User.objects.filter(pk=self.student.pk),
            cohort="Acceptance student",
        )
        expected_percentage_point_gain = round(
            ((posttest_score - pretest_score) / 30) * 100,
            1,
        )
        self.assertEqual(metric["value"], expected_percentage_point_gain)
        self.assertEqual(metric["n"], 1)
        # pre-test, one regular session per lesson record (Lesson 2 has three parts),
        # activity, post-test
        self.assertEqual(
            Session.objects.filter(student=self.student).count(),
            3 + len(lessons),
        )
