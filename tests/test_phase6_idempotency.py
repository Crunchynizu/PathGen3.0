from unittest.mock import patch

from apps.adaptive.models import MasteryEvent
from apps.adaptive.services import process_response
from apps.curriculum.models import QuestionSet
from apps.learning.models import Response, Session, StudentPath
from apps.learning.services.responses import submit_response
from tests.phase6_helpers import Phase6SeededTestCase


class ResponseIdempotencyTests(Phase6SeededTestCase):
    def _one_item_session(self, session_type, *, lesson=None):
        set_type = (
            QuestionSet.SetType.PREPOST
            if session_type == Session.SessionType.POSTTEST
            else QuestionSet.SetType.REGULAR
        )
        return self.make_session_from_set(
            session_type=session_type,
            question_set=self.question_set(set_type, lesson=lesson),
            lesson=lesson,
            limit=1,
        )

    def _submit(self, session):
        item = session.items.get()
        choice = item.question.choices.order_by("display_order").first()
        return submit_response(
            actor=self.student,
            session_id=session.pk,
            session_item_id=item.pk,
            selected_choice_id=choice.pk,
        )

    def test_duplicate_post_returns_committed_state_and_processes_bkt_once(self):
        lesson = self.lesson(1)
        self.set_path(status=StudentPath.Status.LEARNING, stage=StudentPath.Stage.REGULAR, lesson=lesson)
        session = self._one_item_session(Session.SessionType.REGULAR, lesson=lesson)
        with patch(
            "apps.learning.services.responses.process_response",
            wraps=process_response,
        ) as process_bkt:
            first = self._submit(session)
            second = self._submit(session)
        self.assertEqual(first.response.pk, second.response.pk)
        self.assertTrue(second.duplicate)
        self.assertEqual(Response.objects.filter(session_item__session=session).count(), 1)
        process_bkt.assert_called_once()
        self.assertEqual(MasteryEvent.objects.count(), 1)

    def test_posttest_never_calls_bkt_or_creates_event(self):
        self.set_path(
            status=StudentPath.Status.POSTTEST_READY,
            stage=StudentPath.Stage.POSTTEST,
            lesson=self.lesson(3),
        )
        self.setting.posttest_access_enabled = True
        self.setting.save(update_fields=["posttest_access_enabled"])
        session = self._one_item_session(Session.SessionType.POSTTEST)
        with patch("apps.learning.services.responses.process_response") as process_bkt:
            self._submit(session)
        process_bkt.assert_not_called()
        self.assertEqual(MasteryEvent.objects.count(), 0)
