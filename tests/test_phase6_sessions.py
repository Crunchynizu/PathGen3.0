from django.urls import reverse

from apps.curriculum.models import QuestionSet
from apps.learning.models import Session, StudentPath
from apps.learning.services.paths import InvalidPathTransition, transition_path
from apps.learning.services.sessions import PosttestLocked, issue_session
from tests.phase6_helpers import Phase6SeededTestCase


class SessionIssuanceTests(Phase6SeededTestCase):
    def test_invalid_path_transition_is_rejected(self):
        with self.assertRaises(InvalidPathTransition):
            transition_path(
                path=self.path,
                status=StudentPath.Status.COMPLETED,
                current_stage=StudentPath.Stage.POSTTEST,
            )

    def test_pretest_has_exactly_30_fixed_items_and_reissues_same_session(self):
        first = issue_session(actor=self.student, session_type=Session.SessionType.PRETEST)
        second = issue_session(actor=self.student, session_type=Session.SessionType.PRETEST)
        self.assertEqual(first.pk, second.pk)
        self.assertEqual(first.items.count(), 30)
        self.assertEqual(Session.objects.filter(student=self.student).count(), 1)
        self.assertEqual(
            list(first.items.order_by("display_order").values_list("question__code", flat=True)),
            [f"PP-{number:02d}" for number in range(1, 31)],
        )

    def test_regular_has_six_items(self):
        lesson = self.lesson(1)
        self.set_path(status=StudentPath.Status.LEARNING, stage=StudentPath.Stage.REGULAR, lesson=lesson)
        session = issue_session(
            actor=self.student,
            session_type=Session.SessionType.REGULAR,
            lesson=lesson,
        )
        self.assertEqual(session.items.count(), 6)

    def test_foundational_has_three_items_per_weak_skill(self):
        lesson = self.lesson(1)
        self.set_path(status=StudentPath.Status.LEARNING, stage=StudentPath.Stage.FOUNDATIONAL, lesson=lesson)
        session = issue_session(
            actor=self.student,
            session_type=Session.SessionType.FOUNDATIONAL,
            lesson=lesson,
            weak_skills=[self.skill("S1"), self.skill("S5")],
        )
        self.assertEqual(session.items.count(), 6)
        self.assertEqual(
            set(session.items.values_list("question__skill__code", flat=True)),
            {"S1", "S5"},
        )

    def test_activity_has_ten_items(self):
        lesson = self.lesson(3)
        self.set_path(status=StudentPath.Status.ACTIVITY_READY, stage=StudentPath.Stage.ACTIVITY, lesson=lesson)
        session = issue_session(actor=self.student, session_type=Session.SessionType.ACTIVITY)
        self.assertEqual(session.items.count(), 10)

    def test_posttest_requires_access_and_ready_path(self):
        self.set_path(
            status=StudentPath.Status.POSTTEST_READY,
            stage=StudentPath.Stage.POSTTEST,
            lesson=self.lesson(3),
        )
        with self.assertRaises(PosttestLocked):
            issue_session(actor=self.student, session_type=Session.SessionType.POSTTEST)
        self.setting.posttest_access_enabled = True
        self.setting.save(update_fields=["posttest_access_enabled"])
        session = issue_session(actor=self.student, session_type=Session.SessionType.POSTTEST)
        self.assertEqual(session.items.count(), 30)
        prepost = self.question_set(QuestionSet.SetType.PREPOST)
        self.assertEqual(
            list(session.items.order_by("display_order").values_list("question_id", flat=True)),
            list(prepost.items.order_by("display_order").values_list("question_id", flat=True)),
        )

    def test_blocked_posttest_renders_in_page_locked_state(self):
        self.set_path(
            status=StudentPath.Status.POSTTEST_READY,
            stage=StudentPath.Stage.POSTTEST,
            lesson=self.lesson(3),
        )
        self.client.force_login(self.student)
        response = self.client.get(reverse("learning:posttest_overview"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Post-test locked")
        self.assertTemplateUsed(response, "assessment/assessment.html")
