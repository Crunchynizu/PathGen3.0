from collections import defaultdict
from unittest.mock import patch

from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import SystemSetting
from apps.curriculum.models import QuestionSet
from apps.feedback.services import generate_fallback_draft
from apps.learning.models import Response, Session, SessionItem, StudentPath
from apps.learning.services.finalization import finalize_pending_sessions
from apps.learning.services.paths import open_regular_stage
from apps.learning.services.responses import submit_response
from apps.learning.services.sessions import issue_session
from tests.factories import make_user
from tests.phase6_helpers import Phase6SeededTestCase


class ProviderGuardMixin:
    """Fail acceptance tests if either external provider is invoked."""

    def setUp(self):
        super().setUp()
        self._embedding_patcher = patch(
            "apps.feedback.services.OpenAIEmbeddingClient.embed",
            side_effect=AssertionError("Acceptance tests must not call OpenAI."),
        )
        self._groq_patcher = patch(
            "apps.feedback.services.GroqFeedbackClient.generate",
            side_effect=AssertionError("Acceptance tests must not call Groq."),
        )
        self.embedding_mock = self._embedding_patcher.start()
        self.groq_mock = self._groq_patcher.start()
        self.addCleanup(self._embedding_patcher.stop)
        self.addCleanup(self._groq_patcher.stop)

    def tearDown(self):
        self.embedding_mock.assert_not_called()
        self.groq_mock.assert_not_called()
        super().tearDown()


class IntegrationSeededTestCase(ProviderGuardMixin, Phase6SeededTestCase):
    def complete_session(
        self,
        session,
        *,
        correct_total=None,
        correct_per_skill=None,
        hint_used=False,
    ):
        seen_by_skill = defaultdict(int)
        items = list(
            session.items.select_related("question", "question__skill")
            .prefetch_related("question__choices")
            .order_by("display_order")
        )
        result = None
        for index, item in enumerate(items):
            skill_code = item.question.skill.code
            if correct_per_skill is not None:
                should_be_correct = (
                    seen_by_skill[skill_code]
                    < correct_per_skill.get(skill_code, 0)
                )
            elif correct_total is not None:
                should_be_correct = index < correct_total
            else:
                should_be_correct = True
            seen_by_skill[skill_code] += 1
            choices = list(item.question.choices.all())
            choice = next(
                choice
                for choice in choices
                if choice.is_correct is should_be_correct
            )
            result = submit_response(
                actor=self.student,
                session_id=session.pk,
                session_item_id=item.pk,
                selected_choice_id=choice.pk,
                hint_used=hint_used,
            )
        return result

    def finalize_feedback(self, session):
        completed = finalize_pending_sessions(
            feedback_generator=generate_fallback_draft
        )
        self.assertEqual(completed, 1)
        session.refresh_from_db()
        self.assertEqual(session.status, Session.Status.COMPLETED)
        return session

    def complete_pretest(self, *, correct_total=0):
        session = issue_session(
            actor=self.student,
            session_type=Session.SessionType.PRETEST,
        )
        self.complete_session(session, correct_total=correct_total)
        session.refresh_from_db()
        self.path.refresh_from_db()
        return session

    def complete_regular_lesson(self, lesson, *, correct_per_skill=None):
        open_regular_stage(actor=self.student, lesson=lesson)
        session = issue_session(
            actor=self.student,
            session_type=Session.SessionType.REGULAR,
            lesson=lesson,
        )
        self.complete_session(session, correct_per_skill=correct_per_skill)
        self.finalize_feedback(session)
        self.path.refresh_from_db()
        return session

    def complete_activity(self, *, correct_total=10):
        session = issue_session(
            actor=self.student,
            session_type=Session.SessionType.ACTIVITY,
        )
        self.complete_session(session, correct_total=correct_total)
        self.finalize_feedback(session)
        self.path.refresh_from_db()
        return session

    def complete_posttest(self, *, correct_total=30):
        self.setting.posttest_access_enabled = True
        self.setting.save(update_fields=["posttest_access_enabled"])
        session = issue_session(
            actor=self.student,
            session_type=Session.SessionType.POSTTEST,
        )
        self.complete_session(session, correct_total=correct_total)
        session.refresh_from_db()
        self.path.refresh_from_db()
        return session

    def complete_through_activity(self, *, pretest_correct=0):
        sessions = {"pretest": self.complete_pretest(correct_total=pretest_correct)}
        regular = []
        for lesson in self.lessons():
            regular.append(self.complete_regular_lesson(lesson))
        sessions["regular"] = regular
        sessions["activity"] = self.complete_activity()
        return sessions

    def complete_full_path(self, *, pretest_correct=0, posttest_correct=30):
        sessions = self.complete_through_activity(pretest_correct=pretest_correct)
        sessions["posttest"] = self.complete_posttest(
            correct_total=posttest_correct
        )
        return sessions

    def score(self, session):
        return Response.objects.filter(
            session_item__session=session,
            selected_choice__is_correct=True,
        ).count()


def create_completed_assessment(*, student, session_type, correct_total):
    question_set = QuestionSet.objects.get(
        set_type=QuestionSet.SetType.PREPOST,
        is_published=True,
    )
    rows = list(
        question_set.items.select_related("question")
        .prefetch_related("question__choices")
        .order_by("display_order")
    )
    now = timezone.now()
    session = Session.objects.create(
        student=student,
        session_type=session_type,
        status=Session.Status.COMPLETED,
        attempt_number=1,
        started_at=now,
        submitted_at=now,
        completed_at=now,
    )
    for index, row in enumerate(rows, start=1):
        item = SessionItem.objects.create(
            session=session,
            question=row.question,
            display_order=index,
        )
        choices = list(row.question.choices.all())
        should_be_correct = index <= correct_total
        choice = next(
            choice
            for choice in choices
            if choice.is_correct is should_be_correct
        )
        Response.objects.create(session_item=item, selected_choice=choice)
    return session


def create_acceptance_users_and_setting():
    admin = make_user(User.Role.ADMIN)
    student = make_user(User.Role.STUDENT)
    setting = SystemSetting.objects.create(
        singleton_key=1,
        study_access_enabled=True,
        posttest_access_enabled=False,
        changed_by=admin,
        revision=1,
    )
    return admin, student, setting


def create_learning_path(student, lesson):
    return StudentPath.objects.create(
        student=student,
        status=StudentPath.Status.LEARNING,
        current_stage=StudentPath.Stage.REGULAR,
        current_lesson=lesson,
    )
