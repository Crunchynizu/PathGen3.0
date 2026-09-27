from decimal import Decimal

from django.db import DatabaseError, connection, transaction
from django.test import TransactionTestCase
from django.test.utils import CaptureQueriesContext

from apps.adaptive.models import MasteryEvent, SkillMastery
from apps.adaptive.services import process_response
from apps.curriculum.models import QuestionSet
from apps.learning.models import Response, Session, StudentPath
from apps.learning.services.responses import submit_response
from tests.factories import make_response
from tests.phase6_helpers import Phase6SeededTestCase


class MasteryServiceTests(Phase6SeededTestCase):
    def _session(self, session_type, *, hint_used=False):
        lesson = self.lesson(1)
        if session_type == Session.SessionType.REGULAR:
            question_set = self.question_set(QuestionSet.SetType.REGULAR, lesson=lesson)
            self.set_path(
                status=StudentPath.Status.LEARNING,
                stage=StudentPath.Stage.REGULAR,
                lesson=lesson,
            )
        elif session_type == Session.SessionType.FOUNDATIONAL:
            question_set = self.question_set(
                QuestionSet.SetType.FOUNDATIONAL,
                skill=self.skill("S1"),
            )
            self.set_path(
                status=StudentPath.Status.LEARNING,
                stage=StudentPath.Stage.FOUNDATIONAL,
                lesson=lesson,
            )
        else:
            question_set = self.question_set(QuestionSet.SetType.PREPOST)
        session = self.make_session_from_set(
            session_type=session_type,
            question_set=question_set,
            lesson=lesson if session_type in {
                Session.SessionType.REGULAR,
                Session.SessionType.FOUNDATIONAL,
            } else None,
            limit=2,
        )
        item = session.items.get(display_order=1)
        choice = item.question.choices.order_by("display_order").first()
        result = submit_response(
            actor=self.student,
            session_id=session.pk,
            session_item_id=item.pk,
            selected_choice_id=choice.pk,
            hint_used=hint_used,
        )
        return session, result.response

    def test_regular_response_creates_event_and_updates_mastery(self):
        session, response = self._session(Session.SessionType.REGULAR)
        event = MasteryEvent.objects.get(response=response)
        mastery = SkillMastery.objects.get(
            student=self.student,
            skill=response.session_item.question.skill,
        )
        self.assertEqual(event.mastery, mastery)
        self.assertEqual(mastery.evidence_count, 1)
        self.assertNotEqual(mastery.p_known, response.session_item.question.skill.p_l0)
        session.refresh_from_db()
        self.assertEqual(session.status, Session.Status.IN_PROGRESS)

    def test_duplicate_response_does_not_create_or_apply_second_event(self):
        session, response = self._session(Session.SessionType.REGULAR)
        mastery = SkillMastery.objects.get(
            student=self.student,
            skill=response.session_item.question.skill,
        )
        committed_probability = mastery.p_known
        item = response.session_item
        submit_response(
            actor=self.student,
            session_id=session.pk,
            session_item_id=item.pk,
            selected_choice_id=item.question.choices.last().pk,
        )
        process_response(response.pk)
        mastery.refresh_from_db()
        self.assertEqual(MasteryEvent.objects.filter(response=response).count(), 1)
        self.assertEqual(mastery.p_known, committed_probability)
        self.assertEqual(mastery.evidence_count, 1)

    def test_posttest_creates_no_event_and_does_not_touch_mastery(self):
        self.setting.posttest_access_enabled = True
        self.setting.save(update_fields=["posttest_access_enabled"])
        self.set_path(
            status=StudentPath.Status.POSTTEST_READY,
            stage=StudentPath.Stage.POSTTEST,
            lesson=self.lesson(3),
        )
        question_set = self.question_set(QuestionSet.SetType.PREPOST)
        session = self.make_session_from_set(
            session_type=Session.SessionType.POSTTEST,
            question_set=question_set,
            limit=2,
        )
        item = session.items.get(display_order=1)
        mastery = SkillMastery.objects.create(
            student=self.student,
            skill=item.question.skill,
            p_known=Decimal("0.420000"),
            evidence_count=3,
        )
        choice = item.question.choices.first()
        response = submit_response(
            actor=self.student,
            session_id=session.pk,
            session_item_id=item.pk,
            selected_choice_id=choice.pk,
        ).response
        self.assertIsNone(process_response(response.pk))
        mastery.refresh_from_db()
        self.assertEqual(MasteryEvent.objects.filter(response=response).count(), 0)
        self.assertEqual(mastery.p_known, Decimal("0.420000"))
        self.assertEqual(mastery.evidence_count, 3)

    def test_pretest_event_has_no_learning_transition(self):
        _session, response = self._session(Session.SessionType.PRETEST)
        event = MasteryEvent.objects.get(response=response)
        self.assertFalse(event.learning_transition_applied)
        self.assertEqual(event.p_after_observation, event.p_after_learning)

    def test_hinted_foundational_event_skips_observation(self):
        _session, response = self._session(
            Session.SessionType.FOUNDATIONAL,
            hint_used=True,
        )
        event = MasteryEvent.objects.get(response=response)
        self.assertIsNone(event.p_after_observation)
        self.assertTrue(event.learning_transition_applied)
        self.assertTrue(response.hint_used)

    def test_mastery_is_created_lazily_and_locked(self):
        self.assertEqual(SkillMastery.objects.count(), 0)
        with CaptureQueriesContext(connection) as queries:
            _session, response = self._session(Session.SessionType.REGULAR)
        self.assertTrue(
            any(
                "FOR UPDATE" in query["sql"]
                and "adaptive_skill_mastery" in query["sql"]
                for query in queries.captured_queries
            )
        )
        self.assertTrue(
            SkillMastery.objects.filter(
                student=self.student,
                skill=response.session_item.question.skill,
            ).exists()
        )


class Phase7AppendOnlyTests(TransactionTestCase):
    reset_sequences = False

    def setUp(self):
        response = make_response()
        self.event = process_response(response.pk)

    def _assert_rejected(self, sql, params):
        with self.assertRaisesMessage(DatabaseError, "This table is append-only"):
            with transaction.atomic():
                with connection.cursor() as cursor:
                    cursor.execute(sql, params)

    def test_mastery_event_rejects_update(self):
        self._assert_rejected(
            "UPDATE adaptive_mastery_event SET p_before = %s WHERE id = %s",
            ["0.200000", self.event.pk],
        )

    def test_mastery_event_rejects_delete(self):
        self._assert_rejected(
            "DELETE FROM adaptive_mastery_event WHERE id = %s",
            [self.event.pk],
        )
