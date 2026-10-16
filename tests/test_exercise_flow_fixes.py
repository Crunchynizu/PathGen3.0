from unittest.mock import patch

from django.urls import reverse
from django.utils.html import escape

from apps.curriculum.models import QuestionSet
from apps.feedback.models import SessionFeedback
from apps.learning.models import Session, SessionItem, StudentPath
from tests.phase6_helpers import Phase6SeededTestCase


def _offline_generator(session):
    raise RuntimeError("providers are not called in tests")


@patch(
    "apps.learning.services.finalization.generate_session_feedback",
    _offline_generator,
)
class ExerciseFlowFixTests(Phase6SeededTestCase):
    def setUp(self):
        self.lesson_one = self.lesson(1)
        self.set_path(
            status=StudentPath.Status.LEARNING,
            stage=StudentPath.Stage.REGULAR,
            lesson=self.lesson_one,
        )
        self.session = self.make_session_from_set(
            session_type=Session.SessionType.REGULAR,
            question_set=self.question_set(QuestionSet.SetType.REGULAR, lesson=self.lesson_one),
            lesson=self.lesson_one,
        )
        self.client.force_login(self.student)

    def _answer(self, item, *, correct=True):
        choice = item.question.choices.filter(is_correct=correct).first()
        return self.client.post(
            reverse("learning:submit_response", args=[self.session.pk]),
            {"session_item": item.pk, "choice": choice.pk},
        )

    def test_feedback_page_shows_the_number_of_the_answered_question(self):
        first = self.session.items.get(display_order=1)
        response = self.client.get(self._answer(first)["Location"])
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["current_number"], 1)
        self.assertEqual(response.context["total_questions"], 6)

    def test_feedback_stays_on_the_question_with_marked_choices_and_explanation(self):
        first = self.session.items.get(display_order=1)
        response = self.client.get(self._answer(first, correct=False)["Location"])
        self.assertContains(response, escape(first.question.prompt))
        self.assertContains(response, 'data-result="picked-wrong"', count=1)
        self.assertContains(response, 'data-result="correct"', count=1)
        self.assertContains(response, "Correct answer")
        self.assertContains(response, "data-feedback")
        if first.question.explanation:
            self.assertContains(response, escape(first.question.explanation))
        self.assertContains(response, "Next question")

    def test_final_answer_completes_the_session_and_opens_the_result(self):
        for item in self.session.items.order_by("display_order"):
            last = self._answer(item)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, Session.Status.COMPLETED)
        self.assertIsNotNone(self.session.completed_at)
        feedback = SessionFeedback.objects.get(session=self.session)
        self.assertEqual(feedback.generation_status, "fallback")

        feedback_page = self.client.get(last["Location"])
        self.assertEqual(feedback_page.context["current_number"], 6)
        self.assertEqual(
            feedback_page.context["next_url"],
            reverse("learning:assessment_result", args=[self.session.pk]),
        )
        result = self.client.get(reverse("learning:assessment_result", args=[self.session.pk]))
        self.assertEqual(result.status_code, 200)
        self.assertEqual(result.context["mode"], "result")

    def test_a_session_left_submitted_is_recovered_when_reopened(self):
        items = list(self.session.items.order_by("display_order"))
        with patch("apps.learning.views._recover_submitted", lambda session: session):
            for item in items:
                self._answer(item)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, Session.Status.SUBMITTED)

        result = self.client.get(reverse("learning:assessment_result", args=[self.session.pk]))
        self.assertEqual(result.status_code, 200)
        self.session.refresh_from_db()
        self.assertEqual(self.session.status, Session.Status.COMPLETED)
        self.assertTrue(SessionFeedback.objects.filter(session=self.session).exists())

    def test_answered_session_never_renders_an_empty_question_form(self):
        items = list(self.session.items.order_by("display_order"))
        with patch("apps.learning.views._recover_submitted", lambda session: session):
            for item in items:
                self._answer(item)
            response = self.client.get(
                reverse("learning:assessment_session", args=[self.session.pk])
            )
        self.assertRedirects(response, reverse("account:my_lesson"), fetch_redirect_response=False)
        self.assertFalse(SessionItem.objects.filter(session=self.session, response__isnull=True).exists())
