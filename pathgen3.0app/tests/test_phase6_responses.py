from django.urls import reverse

from apps.curriculum.models import QuestionSet
from apps.learning.models import Response, Session, StudentPath
from apps.learning.services.responses import (
    HintNotAllowed,
    OutOfOrderResponse,
    submit_response,
)
from tests.factories import make_user
from tests.phase6_helpers import Phase6SeededTestCase


class ResponseServiceTests(Phase6SeededTestCase):
    def _session(self, session_type, *, lesson=None, limit=2):
        set_type = {
            Session.SessionType.PRETEST: QuestionSet.SetType.PREPOST,
            Session.SessionType.POSTTEST: QuestionSet.SetType.PREPOST,
            Session.SessionType.REGULAR: QuestionSet.SetType.REGULAR,
            Session.SessionType.FOUNDATIONAL: QuestionSet.SetType.FOUNDATIONAL,
            Session.SessionType.ACTIVITY: QuestionSet.SetType.ACTIVITY,
        }[session_type]
        skill = self.skill("S1") if session_type == Session.SessionType.FOUNDATIONAL else None
        question_set = self.question_set(set_type, lesson=lesson if set_type == "regular" else None, skill=skill)
        return self.make_session_from_set(
            session_type=session_type,
            question_set=question_set,
            lesson=lesson,
            limit=limit,
        )

    def _answer(self, session, order=1, *, hint=False):
        item = session.items.get(display_order=order)
        choice = item.question.choices.order_by("display_order").first()
        return submit_response(
            actor=self.student,
            session_id=session.pk,
            session_item_id=item.pk,
            selected_choice_id=choice.pk,
            hint_used=hint,
        )

    def test_out_of_order_is_rejected(self):
        session = self._session(Session.SessionType.PRETEST)
        item = session.items.get(display_order=2)
        choice = item.question.choices.first()
        with self.assertRaises(OutOfOrderResponse):
            submit_response(
                actor=self.student,
                session_id=session.pk,
                session_item_id=item.pk,
                selected_choice_id=choice.pk,
            )

    def test_hint_only_accepted_for_foundational(self):
        regular_lesson = self.lesson(1)
        regular = self._session(Session.SessionType.REGULAR, lesson=regular_lesson)
        with self.assertRaises(HintNotAllowed):
            self._answer(regular, hint=True)

        foundational = self._session(
            Session.SessionType.FOUNDATIONAL,
            lesson=regular_lesson,
            limit=1,
        )
        self.set_path(
            status=StudentPath.Status.LEARNING,
            stage=StudentPath.Stage.FOUNDATIONAL,
            lesson=regular_lesson,
        )
        result = self._answer(foundational, hint=True)
        self.assertTrue(result.response.hint_used)

    def test_foreign_session_returns_404(self):
        session = self._session(Session.SessionType.PRETEST)
        outsider = make_user()
        self.client.force_login(outsider)
        response = self.client.get(
            reverse("learning:assessment_session", args=[session.pk])
        )
        self.assertEqual(response.status_code, 404)

    def test_required_path_transitions(self):
        pretest = self._session(Session.SessionType.PRETEST, limit=1)
        self._answer(pretest)
        self.path.refresh_from_db()
        self.assertEqual(self.path.status, StudentPath.Status.LEARNING)
        self.assertEqual(self.path.current_lesson.lesson_order, 1)

        # passing the last lesson part's exercise opens the activity
        lesson3 = self.lessons()[-1]
        self.set_path(status=StudentPath.Status.LEARNING, stage=StudentPath.Stage.REGULAR, lesson=lesson3)
        regular = self._session(Session.SessionType.REGULAR, lesson=lesson3, limit=6)
        for item in regular.items.order_by("display_order"):
            submit_response(
                actor=self.student,
                session_id=regular.pk,
                session_item_id=item.pk,
                selected_choice_id=item.question.choices.get(is_correct=True).pk,
                hint_used=False,
            )
        self.path.refresh_from_db()
        self.assertEqual(self.path.status, StudentPath.Status.ACTIVITY_READY)

        activity = self._session(Session.SessionType.ACTIVITY, limit=1)
        self._answer(activity)
        self.path.refresh_from_db()
        self.assertEqual(self.path.status, StudentPath.Status.POSTTEST_READY)

        self.setting.posttest_access_enabled = True
        self.setting.save(update_fields=["posttest_access_enabled"])
        posttest = self._session(Session.SessionType.POSTTEST, limit=1)
        self._answer(posttest)
        self.path.refresh_from_db()
        self.assertEqual(self.path.status, StudentPath.Status.COMPLETED)
        self.assertEqual(Response.objects.filter(session_item__session=posttest).count(), 1)
