import inspect
from unittest.mock import patch

from django.core.exceptions import PermissionDenied

from apps.adaptive.models import Decision, MasteryEvent
from apps.feedback.models import SessionFeedback
from apps.learning import views
from apps.learning.models import Response, Session, StudentPath
from apps.learning.services.responses import (
    InvalidChoice,
    SessionNotOpen,
    submit_response,
)
from tests.phase9_helpers import Phase9SeededTestCase


class FailureMatrixTests(Phase9SeededTestCase):
    def _assert_no_final_side_effects(self, session):
        self.assertFalse(Decision.objects.filter(session=session).exists())
        self.assertFalse(SessionFeedback.objects.filter(session=session).exists())
        self.path.refresh_from_db()
        self.assertEqual(self.path.current_stage, StudentPath.Stage.REGULAR)
        self.assertEqual(self.path.current_lesson_id, session.lesson_id)

    def test_bkt_error_rolls_back_only_failing_response(self):
        session = self.exercise_session(Session.SessionType.REGULAR)
        items = list(session.items.select_related("question").order_by("display_order"))
        self.submit_item(session, items[0])
        with patch(
            "apps.learning.services.responses.process_response",
            side_effect=RuntimeError("injected BKT failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "injected BKT failure"):
                self.submit_item(session, items[1])
        session.refresh_from_db()
        self.assertEqual(session.status, Session.Status.IN_PROGRESS)
        self.assertEqual(Response.objects.filter(session_item__session=session).count(), 1)
        self.assertEqual(
            MasteryEvent.objects.filter(
                response__session_item__session=session
            ).count(),
            1,
        )
        self._assert_no_final_side_effects(session)

    def test_q_learning_error_rolls_back_final_transaction(self):
        session = self.exercise_session(Session.SessionType.REGULAR)
        last = self.submit_before_last(session)
        with patch(
            "apps.adaptive.services.decide",
            side_effect=RuntimeError("injected Q-Learning failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "injected Q-Learning failure"):
                self.submit_item(session, last)
        session.refresh_from_db()
        self.assertEqual(session.status, Session.Status.IN_PROGRESS)
        self.assertEqual(Response.objects.filter(session_item__session=session).count(), 5)
        self.assertEqual(
            MasteryEvent.objects.filter(
                response__session_item__session=session
            ).count(),
            5,
        )
        self._assert_no_final_side_effects(session)

    def test_path_transition_error_rolls_back_everything(self):
        session = self.exercise_session(Session.SessionType.REGULAR)
        last = self.submit_before_last(session)
        with patch(
            "apps.learning.services.finalization.transition_path",
            side_effect=RuntimeError("injected path failure"),
        ):
            with self.assertRaisesRegex(RuntimeError, "injected path failure"):
                self.submit_item(session, last)
        session.refresh_from_db()
        self.assertEqual(session.status, Session.Status.IN_PROGRESS)
        self.assertEqual(Response.objects.filter(session_item__session=session).count(), 5)
        self.assertEqual(
            MasteryEvent.objects.filter(
                response__session_item__session=session
            ).count(),
            5,
        )
        self._assert_no_final_side_effects(session)

    def test_validation_error_before_write_leaves_no_rows(self):
        session = self.exercise_session(Session.SessionType.REGULAR)
        items = list(session.items.select_related("question").order_by("display_order"))
        wrong_choice = items[1].question.choices.first()
        with self.assertRaises(InvalidChoice):
            submit_response(
                actor=self.student,
                session_id=session.pk,
                session_item_id=items[0].pk,
                selected_choice_id=wrong_choice.pk,
            )
        self.assertFalse(Response.objects.filter(session_item__session=session).exists())
        self.assertFalse(MasteryEvent.objects.exists())
        self._assert_no_final_side_effects(session)

    def test_stale_path_is_denied_before_write(self):
        session = self.exercise_session(Session.SessionType.REGULAR)
        self.path.current_stage = StudentPath.Stage.LESSON
        self.path.save(update_fields=["current_stage", "updated_at"])
        item = session.items.select_related("question").order_by("display_order").first()
        choice = item.question.choices.get(is_correct=True)
        with self.assertRaises(SessionNotOpen):
            submit_response(
                actor=self.student,
                session_id=session.pk,
                session_item_id=item.pk,
                selected_choice_id=choice.pk,
            )
        self.assertFalse(Response.objects.filter(session_item__session=session).exists())
        self.assertFalse(MasteryEvent.objects.exists())
        self.assertFalse(Decision.objects.filter(session=session).exists())

    def test_closed_study_access_is_denied_before_write(self):
        session = self.exercise_session(Session.SessionType.REGULAR)
        self.setting.study_access_enabled = False
        self.setting.save(update_fields=["study_access_enabled"])
        item = session.items.select_related("question").order_by("display_order").first()
        choice = item.question.choices.get(is_correct=True)
        with self.assertRaises(PermissionDenied):
            submit_response(
                actor=self.student,
                session_id=session.pk,
                session_item_id=item.pk,
                selected_choice_id=choice.pk,
            )
        self.assertFalse(Response.objects.filter(session_item__session=session).exists())
        self.assertFalse(MasteryEvent.objects.exists())
        self.assertFalse(Decision.objects.filter(session=session).exists())

    def test_views_do_not_acquire_row_locks(self):
        self.assertNotIn("select_for_update", inspect.getsource(views))
