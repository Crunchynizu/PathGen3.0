from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from django.core.management import call_command
from django.db import close_old_connections, transaction
from django.test import TransactionTestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.adaptive.models import Decision, MasteryEvent
from apps.adaptive.services import process_response
from apps.core.models import SystemSetting
from apps.curriculum.models import Lesson, QuestionSet
from apps.feedback.models import SessionFeedback
from apps.learning.models import Response, Session, SessionItem, StudentPath
from apps.learning.services.finalization import (
    finalize_locked_session,
    finalize_pending_sessions,
)
from apps.learning.services.responses import submit_response
from tests.factories import make_user


class OrchestratorConcurrencyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self):
        call_command("seed_curriculum", verbosity=0)
        self.admin = make_user(User.Role.ADMIN)
        self.student = make_user(User.Role.STUDENT)
        SystemSetting.objects.create(
            singleton_key=1,
            study_access_enabled=True,
            posttest_access_enabled=False,
            changed_by=self.admin,
            revision=1,
        )
        self.lesson = Lesson.objects.get(lesson_order=1)
        self.path = StudentPath.objects.create(
            student=self.student,
            status=StudentPath.Status.LEARNING,
            current_stage=StudentPath.Stage.REGULAR,
            current_lesson=self.lesson,
        )

    def _session(self, *, limit=None):
        question_set = QuestionSet.objects.get(
            set_type=QuestionSet.SetType.REGULAR,
            lesson=self.lesson,
            is_published=True,
        )
        rows = list(question_set.items.select_related("question").order_by("display_order"))
        if limit is not None:
            rows = rows[:limit]
        session = Session.objects.create(
            student=self.student,
            session_type=Session.SessionType.REGULAR,
            lesson=self.lesson,
            status=Session.Status.ISSUED,
            attempt_number=1,
        )
        SessionItem.objects.bulk_create(
            [
                SessionItem(
                    session=session,
                    question=row.question,
                    display_order=index,
                )
                for index, row in enumerate(rows, start=1)
            ]
        )
        return session

    def _run_threads(self, worker):
        barrier = Barrier(2)

        def wrapped():
            close_old_connections()
            try:
                barrier.wait(timeout=10)
                return worker()
            finally:
                close_old_connections()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(wrapped) for _ in range(2)]
            return [future.result(timeout=20) for future in futures]

    def test_two_simultaneous_responses_serialize(self):
        session = self._session(limit=1)
        item = session.items.select_related("question").get()
        choice = item.question.choices.get(is_correct=True)

        def worker():
            actor = User.objects.get(pk=self.student.pk)
            return submit_response(
                actor=actor,
                session_id=session.pk,
                session_item_id=item.pk,
                selected_choice_id=choice.pk,
            ).duplicate

        duplicates = self._run_threads(worker)
        self.assertEqual(sorted(duplicates), [False, True])
        self.assertEqual(Response.objects.filter(session_item__session=session).count(), 1)
        self.assertEqual(
            MasteryEvent.objects.filter(
                response__session_item__session=session
            ).count(),
            1,
        )

    def test_two_simultaneous_finalizations_create_one_decision(self):
        session = self._session()
        for item in session.items.select_related("question").order_by("display_order"):
            response = Response.objects.create(
                session_item=item,
                selected_choice=item.question.choices.get(is_correct=True),
            )
            process_response(response.pk)

        def worker():
            with transaction.atomic():
                StudentPath.objects.select_for_update(of=("self",)).get(
                    student_id=self.student.pk
                )
                locked_session = Session.objects.select_for_update(of=("self",)).get(
                    pk=session.pk
                )
                locked_path = StudentPath.objects.get(student_id=self.student.pk)
                finalize_locked_session(
                    session=locked_session,
                    path=locked_path,
                )
                return locked_session.status

        statuses = self._run_threads(worker)
        self.assertEqual(statuses, [Session.Status.SUBMITTED] * 2)
        self.assertEqual(Decision.objects.filter(session=session).count(), 1)

    def test_concurrent_pending_finalizers_do_not_duplicate_feedback(self):
        session = self._session(limit=1)
        session.status = Session.Status.SUBMITTED
        session.submitted_at = timezone.now()
        session.save(update_fields=["status", "submitted_at", "updated_at"])

        counts = self._run_threads(finalize_pending_sessions)
        self.assertEqual(sum(counts), 1)
        self.assertEqual(SessionFeedback.objects.filter(session=session).count(), 1)
        session.refresh_from_db()
        self.assertEqual(session.status, Session.Status.COMPLETED)
