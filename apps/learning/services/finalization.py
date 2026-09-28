from django.db import transaction
from django.utils import timezone

from apps.adaptive.models import Decision, MasteryEvent, SkillMastery
from apps.adaptive.services import persist_session_decision
from apps.curriculum.models import Lesson
from apps.feedback.models import SessionFeedback
from apps.feedback.services import (
    generate_fallback_draft,
    generate_session_feedback,
)
from apps.learning.models import Response, Session, SessionItem, StudentPath
from apps.learning.services.paths import transition_path


RAG_ELIGIBLE_TYPES = {
    Session.SessionType.REGULAR,
    Session.SessionType.ADDITIONAL,
    Session.SessionType.FOUNDATIONAL,
    Session.SessionType.ACTIVITY,
}

class SessionFinalizationError(ValueError):
    pass


def _verify_complete_evidence(session):
    issued_count = SessionItem.objects.filter(session=session).count()
    response_count = Response.objects.filter(session_item__session=session).count()
    if issued_count == 0 or response_count != issued_count:
        raise SessionFinalizationError("The session cannot be finalized yet.")

    event_count = MasteryEvent.objects.filter(
        response__session_item__session=session
    ).count()
    if session.session_type == Session.SessionType.POSTTEST:
        if event_count:
            raise SessionFinalizationError(
                "Post-test responses must not have mastery events."
            )
    elif event_count != response_count:
        raise SessionFinalizationError(
            "Every eligible response must have one mastery event."
        )


def _lock_session_masteries(session):
    if session.session_type == Session.SessionType.POSTTEST:
        return
    skill_ids = SessionItem.objects.filter(session=session).values_list(
        "question__skill_id",
        flat=True,
    ).distinct()
    list(
        SkillMastery.objects.select_for_update(of=("self",))
        .filter(student_id=session.student_id, skill_id__in=skill_ids)
        .order_by("skill_id")
    )


def _apply_progress_transition(*, session, path):
    next_lesson = (
        Lesson.objects.filter(
            is_published=True,
            lesson_order__gt=session.lesson.lesson_order,
        )
        .order_by("lesson_order")
        .first()
    )
    if next_lesson is None:
        return transition_path(
            path=path,
            status=StudentPath.Status.ACTIVITY_READY,
            current_stage=StudentPath.Stage.ACTIVITY,
            current_lesson=session.lesson,
        )
    return transition_path(
        path=path,
        status=StudentPath.Status.LEARNING,
        current_stage=StudentPath.Stage.LESSON,
        current_lesson=next_lesson,
    )


def finalize_locked_session(*, session, path):
    """Finalize while the caller holds path then session row locks."""
    if session.status == Session.Status.COMPLETED:
        return session
    if (
        session.status == Session.Status.SUBMITTED
        and Decision.objects.filter(session=session).exists()
    ):
        return session

    _lock_session_masteries(session)
    _verify_complete_evidence(session)

    decision = None
    if session.session_type in RAG_ELIGIBLE_TYPES:
        decision = persist_session_decision(session)

    if session.session_type == Session.SessionType.PRETEST:
        first_lesson = Lesson.objects.filter(is_published=True).order_by(
            "lesson_order"
        ).first()
        if first_lesson is None:
            raise SessionFinalizationError("The first lesson is not available.")
        transition_path(
            path=path,
            status=StudentPath.Status.LEARNING,
            current_stage=StudentPath.Stage.LESSON,
            current_lesson=first_lesson,
        )
    elif session.session_type in {
        Session.SessionType.REGULAR,
        Session.SessionType.ADDITIONAL,
        Session.SessionType.FOUNDATIONAL,
    }:
        if decision.action == Decision.Action.PROGRESS:
            _apply_progress_transition(session=session, path=path)
        else:
            transition_path(
                path=path,
                status=StudentPath.Status.LEARNING,
                current_stage=(
                    StudentPath.Stage.ADDITIONAL
                    if decision.action == Decision.Action.ADDITIONAL_EXERCISE
                    else StudentPath.Stage.FOUNDATIONAL
                ),
                current_lesson=session.lesson,
            )
    elif session.session_type == Session.SessionType.ACTIVITY:
        transition_path(
            path=path,
            status=StudentPath.Status.POSTTEST_READY,
            current_stage=StudentPath.Stage.POSTTEST,
            current_lesson=path.current_lesson,
        )
    elif session.session_type == Session.SessionType.POSTTEST:
        transition_path(
            path=path,
            status=StudentPath.Status.COMPLETED,
            current_stage=StudentPath.Stage.POSTTEST,
            current_lesson=path.current_lesson,
        )

    now = timezone.now()
    session.submitted_at = session.submitted_at or now
    if session.session_type in RAG_ELIGIBLE_TYPES:
        session.status = Session.Status.SUBMITTED
        session.completed_at = None
        update_fields = ["status", "submitted_at", "completed_at", "updated_at"]
    else:
        session.status = Session.Status.COMPLETED
        session.completed_at = now
        update_fields = ["status", "submitted_at", "completed_at", "updated_at"]
    session.save(update_fields=update_fields)
    return session


def _pending_session_ids():
    return list(
        Session.objects.filter(
            status=Session.Status.SUBMITTED,
            submitted_at__isnull=False,
        )
        .order_by("created_at", "pk")
        .values_list("pk", flat=True)
    )


def _mark_completed(session):
    session.status = Session.Status.COMPLETED
    session.completed_at = timezone.now()
    session.save(update_fields=["status", "completed_at", "updated_at"])


def finalize_pending_sessions(*, feedback_generator=None):
    """Generate feedback outside locks, then persist it in a short transaction."""
    feedback_generator = feedback_generator or generate_session_feedback
    completed = 0
    for session_id in _pending_session_ids():
        session = Session.objects.select_related("lesson").filter(pk=session_id).first()
        if session is None:
            continue

        draft = None
        if (
            session.session_type in RAG_ELIGIBLE_TYPES
            and not SessionFeedback.objects.filter(session_id=session_id).exists()
        ):
            try:
                draft = feedback_generator(session)
            except Exception:
                draft = generate_fallback_draft(session)

        with transaction.atomic():
            session = Session.objects.select_for_update(of=("self",)).get(
                pk=session_id
            )
            if (
                session.status != Session.Status.SUBMITTED
                or session.submitted_at is None
            ):
                continue

            if session.session_type not in RAG_ELIGIBLE_TYPES:
                _mark_completed(session)
                completed += 1
                continue

            if not SessionFeedback.objects.filter(session=session).exists():
                if draft is None:
                    draft = generate_fallback_draft(session)
                SessionFeedback.objects.bulk_create(
                    [
                        SessionFeedback(
                            session=session,
                            feedback_text=draft.feedback_text,
                            generation_status=draft.generation_status,
                            model_name=draft.model_name,
                        )
                    ],
                    ignore_conflicts=True,
                )
            if not SessionFeedback.objects.filter(session=session).exists():
                continue
            _mark_completed(session)
            completed += 1
    return completed
