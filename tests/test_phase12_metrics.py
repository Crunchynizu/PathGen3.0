from datetime import timedelta

from django.apps import apps
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import User
from apps.core import metrics
from apps.feedback.models import SessionFeedback
from apps.learning.models import Session, StudentPath
from tests.factories import (
    make_choice,
    make_feedback,
    make_question,
    make_response,
    make_session,
    make_session_item,
    make_student_path,
    make_user,
)


def completed_scored_session(student, session_type, answers, *, started_at=None, completed_at=None):
    completed_at = completed_at or timezone.now()
    started_at = started_at or completed_at - timedelta(minutes=10)
    session = make_session(
        student=student,
        session_type=session_type,
        status=Session.Status.COMPLETED,
        started_at=started_at,
        submitted_at=completed_at,
        completed_at=completed_at,
    )
    for order, is_correct in enumerate(answers, start=1):
        question = make_question()
        item = make_session_item(session=session, question=question, display_order=order)
        choice = make_choice(
            question=question,
            label="A",
            display_order=1,
            is_correct=is_correct,
        )
        make_response(session_item=item, selected_choice=choice)
    return session


class Phase12MetricsTests(TestCase):
    def setUp(self):
        self.student = make_user(User.Role.STUDENT)
        self.students = User.objects.filter(pk=self.student.pk)

    def test_01_every_metric_has_required_metadata(self):
        metric_functions = [
            metrics.active_students,
            metrics.completed_paths,
            metrics.matched_prepost_sample,
            metrics.matched_gain,
            metrics.bkt_mastery_bands,
            metrics.q_learning_decisions,
            metrics.follow_up_needed,
            metrics.median_elapsed_duration,
            metrics.rag_reliability,
        ]
        for metric_function in metric_functions:
            result = metric_function(self.students, cohort="Test cohort")
            self.assertTrue(
                {"cohort", "n", "definition", "window", "version"}.issubset(result),
                metric_function.__name__,
            )
            self.assertEqual(result["version"], "METRICS-V1")

    def test_02_empty_cohort_is_insufficient_not_zero(self):
        empty = User.objects.filter(pk__isnull=True)
        metric_functions = [
            metrics.active_students,
            metrics.completed_paths,
            metrics.matched_prepost_sample,
            metrics.matched_gain,
            metrics.bkt_mastery_bands,
            metrics.q_learning_decisions,
            metrics.follow_up_needed,
            metrics.median_elapsed_duration,
            metrics.rag_reliability,
        ]
        for metric_function in metric_functions:
            result = metric_function(empty)
            self.assertIsNone(result["value"], metric_function.__name__)
            self.assertEqual(result["n"], 0, metric_function.__name__)
            self.assertTrue(result["insufficient"], metric_function.__name__)

    def test_03_matched_gain_excludes_unmatched_tests(self):
        completed_scored_session(self.student, Session.SessionType.PRETEST, [True, False])
        completed_scored_session(self.student, Session.SessionType.POSTTEST, [True, True])
        unmatched = make_user(User.Role.STUDENT)
        completed_scored_session(unmatched, Session.SessionType.POSTTEST, [False, False])
        students = User.objects.filter(pk__in=[self.student.pk, unmatched.pk])

        result = metrics.matched_gain(students)

        self.assertEqual(result["n"], 1)
        self.assertEqual(result["value"], 50.0)

    def test_04_median_elapsed_uses_completed_minus_started(self):
        now = timezone.now()
        completed_scored_session(
            self.student,
            Session.SessionType.REGULAR,
            [True],
            started_at=now - timedelta(minutes=10),
            completed_at=now,
        )
        completed_scored_session(
            self.student,
            Session.SessionType.REGULAR,
            [True],
            started_at=now - timedelta(minutes=20),
            completed_at=now,
        )

        result = metrics.median_elapsed_duration(self.students)

        self.assertEqual(result["value"]["Regular"], 15.0)

    def test_05_rag_reliability_counts_generated_and_fallback(self):
        generated = make_session(student=self.student)
        fallback = make_session(student=self.student, attempt_number=2)
        make_feedback(
            session=generated,
            generation_status=SessionFeedback.GenerationStatus.GENERATED,
            model_name="gpt-oss-120b",
        )
        make_feedback(
            session=fallback,
            generation_status=SessionFeedback.GenerationStatus.FALLBACK,
            model_name=None,
        )

        result = metrics.rag_reliability(self.students)

        self.assertEqual(result["value"], {"generated": 1, "fallback": 1})
        self.assertEqual(result["n"], 2)

    def test_06_derived_metric_names_are_not_model_fields(self):
        derived_names = {
            "matched_gain",
            "bkt_mastery_bands",
            "q_learning_decisions",
            "median_elapsed_duration",
            "rag_reliability",
        }
        field_names = {
            field.name
            for model in apps.get_models()
            for field in model._meta.local_fields
        }
        self.assertTrue(derived_names.isdisjoint(field_names))
