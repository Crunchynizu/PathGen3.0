from django.urls import reverse

from apps.curriculum.models import Question, QuestionSet, Video
from apps.learning.models import Session, SessionItem, StudentPath
from apps.learning.services.responses import submit_response
from tests.phase6_helpers import Phase6SeededTestCase


class FeedbackRuleTests(Phase6SeededTestCase):
    def _submit_first(self, session):
        item = session.items.get(display_order=1)
        choice = item.question.choices.order_by("display_order").first()
        return submit_response(
            actor=self.student,
            session_id=session.pk,
            session_item_id=item.pk,
            selected_choice_id=choice.pk,
        )

    def test_pretest_context_does_not_reveal_correctness(self):
        session = self.make_session_from_set(
            session_type=Session.SessionType.PRETEST,
            question_set=self.question_set(QuestionSet.SetType.PREPOST),
            limit=2,
        )
        self._submit_first(session)
        self.client.force_login(self.student)
        response = self.client.get(reverse("learning:assessment_session", args=[session.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["feedback"])
        self.assertNotContains(response, "Answer saved")
        saved_response = self.client.get(
            f"{reverse('learning:assessment_session', args=[session.pk])}?saved=1"
        )
        self.assertContains(saved_response, "Answer saved.")
        self.assertNotContains(saved_response, "Not quite")

    def test_regular_context_reveals_immediate_feedback(self):
        lesson = self.lesson(1)
        self.set_path(status=StudentPath.Status.LEARNING, stage=StudentPath.Stage.REGULAR, lesson=lesson)
        session = self.make_session_from_set(
            session_type=Session.SessionType.REGULAR,
            question_set=self.question_set(QuestionSet.SetType.REGULAR, lesson=lesson),
            lesson=lesson,
            limit=2,
        )
        result = self._submit_first(session)
        self.client.force_login(self.student)
        url = reverse("learning:assessment_session", args=[session.pk])
        response = self.client.get(f"{url}?feedback={result.response.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertIn("is_correct", response.context["feedback"])
        self.assertContains(response, "Answer saved")

    def test_my_lesson_renders_all_state_labels_and_hides_unassigned_branches(self):
        lesson = self.lesson(1)
        self.set_path(status=StudentPath.Status.LEARNING, stage=StudentPath.Stage.LESSON, lesson=lesson)
        self.client.force_login(self.student)
        response = self.client.get(reverse("account:my_lesson"))
        self.assertEqual(response.status_code, 200)
        for label in ("completed", "current", "available", "locked"):
            self.assertContains(response, label)
        self.assertNotContains(response, "Additional Exercise")
        self.assertNotContains(response, "Foundational Exercise")

    def test_posttest_locked_state_is_not_error_template(self):
        self.client.force_login(self.student)
        response = self.client.get(reverse("learning:posttest_overview"))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, "assessment/assessment.html")
        self.assertNotContains(response, "error.html")

    def _video_question_session(self):
        question = Question.objects.get(code="ACT-S5-01")
        session = Session.objects.create(
            student=self.student,
            session_type=Session.SessionType.ACTIVITY,
            status=Session.Status.IN_PROGRESS,
            attempt_number=1,
        )
        SessionItem.objects.create(session=session, question=question, display_order=1)
        self.client.force_login(self.student)
        return session

    def test_video_question_with_hidden_video_shows_question_and_transcript(self):
        # Its number-line video was removed from YouTube, so the manifest no longer lists an ID.
        session = self._video_question_session()
        response = self.client.get(reverse("learning:assessment_session", args=[session.pk]))
        self.assertContains(response, "Video not yet available")
        self.assertContains(response, "content_source/transcripts/VID-INTEGER-NUMBER-LINE.txt")
        self.assertNotContains(response, "youtube-nocookie.com/embed/")
        self.assertNotContains(response, "Continue to question without watching")
        self.assertContains(response, "data-video-question")

    def test_video_question_has_bounded_cue_transcript_and_optional_watch(self):
        # The cue mechanism, checked with a video that is still on YouTube.
        Question.objects.filter(code="ACT-S5-01").update(
            video=Video.objects.get(code="VID-INTEGER-ADD-SUBTRACT")
        )
        question = Question.objects.get(code="ACT-S5-01")
        session = Session.objects.create(
            student=self.student,
            session_type=Session.SessionType.ACTIVITY,
            status=Session.Status.IN_PROGRESS,
            attempt_number=1,
        )
        SessionItem.objects.create(session=session, question=question, display_order=1)
        self.client.force_login(self.student)
        response = self.client.get(reverse("learning:assessment_session", args=[session.pk]))
        self.assertContains(response, 'data-pause-seconds="110"')
        self.assertContains(response, 'start=80&amp;end=125')  # the borrowed video's clip bounds
        self.assertContains(response, "content_source/transcripts/VID-INTEGER-ADD-SUBTRACT.txt")
        self.assertContains(response, "data-video-question")
        self.assertNotContains(response, "data-video-question hidden")
        self.assertContains(response, "Continue to question without watching")

    def test_exit_confirmation_does_not_submit_remaining_items(self):
        session = self.make_session_from_set(
            session_type=Session.SessionType.PRETEST,
            question_set=self.question_set(QuestionSet.SetType.PREPOST),
            limit=2,
        )
        session.status = Session.Status.IN_PROGRESS
        session.save(update_fields=["status"])
        self.client.force_login(self.student)
        response = self.client.get(reverse("learning:assessment_session", args=[session.pk]))
        self.assertContains(response, "Exit assessment")
        self.assertContains(response, "Your answers so far are saved. You can resume this assessment later.")
        session.refresh_from_db()
        self.assertEqual(session.status, Session.Status.IN_PROGRESS)
        self.assertIsNone(session.submitted_at)
