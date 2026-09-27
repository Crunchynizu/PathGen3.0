from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.adaptive.models import Decision
from apps.adaptive.services import persist_session_decision, process_response
from apps.core.models import SystemSetting
from apps.curriculum.models import Lesson, QuestionChoice
from apps.learning.models import Response, Session, SessionItem, StudentPath
from apps.learning.services.paths import transition_path


class ResponseSubmissionError(ValueError):
    pass


class SessionNotOpen(ResponseSubmissionError):
    pass


class OutOfOrderResponse(ResponseSubmissionError):
    pass


class InvalidChoice(ResponseSubmissionError):
    pass


class HintNotAllowed(ResponseSubmissionError):
    pass


@dataclass(frozen=True)
class SubmissionResult:
    response: Response
    session: Session
    is_correct: bool
    feedback_allowed: bool
    duplicate: bool = False


IMMEDIATE_FEEDBACK_TYPES = {
    Session.SessionType.REGULAR,
    Session.SessionType.ADDITIONAL,
    Session.SessionType.FOUNDATIONAL,
    Session.SessionType.ACTIVITY,
}


def _require_student(actor):
    if not actor.is_active or actor.role != User.Role.STUDENT:
        raise PermissionDenied


def _result(response, session, *, duplicate=False):
    return SubmissionResult(
        response=response,
        session=session,
        is_correct=response.selected_choice.is_correct,
        feedback_allowed=session.session_type in IMMEDIATE_FEEDBACK_TYPES,
        duplicate=duplicate,
    )


def _finalize(*, session):
    issued_count = SessionItem.objects.filter(session=session).count()
    response_count = Response.objects.filter(session_item__session=session).count()
    if issued_count == 0 or response_count != issued_count:
        raise ResponseSubmissionError("The session cannot be finalized yet.")

    path = (
        StudentPath.objects.select_for_update(of=("self",))
        .select_related("current_lesson")
        .get(student=session.student)
    )
    now = timezone.now()
    session.status = Session.Status.COMPLETED
    session.submitted_at = now
    session.completed_at = now
    session.save(update_fields=["status", "submitted_at", "completed_at", "updated_at"])

    decision = None
    if session.session_type in {
        Session.SessionType.REGULAR,
        Session.SessionType.ADDITIONAL,
        Session.SessionType.FOUNDATIONAL,
        Session.SessionType.ACTIVITY,
    }:
        decision = persist_session_decision(session)

    if session.session_type == Session.SessionType.PRETEST:
        first_lesson = Lesson.objects.filter(is_published=True).order_by("lesson_order").first()
        if first_lesson is None:
            raise ResponseSubmissionError("The first lesson is not available.")
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
    } and decision.action == Decision.Action.PROGRESS:
        next_lesson = (
            Lesson.objects.filter(
                is_published=True,
                lesson_order__gt=session.lesson.lesson_order,
            )
            .order_by("lesson_order")
            .first()
        )
        if next_lesson is None:
            transition_path(
                path=path,
                status=StudentPath.Status.ACTIVITY_READY,
                current_stage=StudentPath.Stage.ACTIVITY,
                current_lesson=session.lesson,
            )
        else:
            transition_path(
                path=path,
                status=StudentPath.Status.LEARNING,
                current_stage=StudentPath.Stage.LESSON,
                current_lesson=next_lesson,
            )
    elif decision is not None and decision.action in {
        Decision.Action.ADDITIONAL_EXERCISE,
        Decision.Action.FOUNDATIONAL_EXERCISE,
    }:
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


@transaction.atomic
def submit_response(*, actor, session_id, session_item_id, selected_choice_id, hint_used=False):
    _require_student(actor)
    session = (
        Session.objects.select_for_update(of=("self",))
        .select_related("student", "lesson")
        .get(pk=session_id)
    )
    if session.student_id != actor.pk:
        raise PermissionDenied

    try:
        item = SessionItem.objects.select_related("question").get(
            pk=session_item_id,
            session=session,
        )
    except SessionItem.DoesNotExist as exc:
        raise OutOfOrderResponse("The question does not belong to this session.") from exc

    existing = (
        Response.objects.select_related("selected_choice", "session_item")
        .filter(session_item=item)
        .first()
    )
    if existing is not None:
        return _result(existing, session, duplicate=True)

    if not SystemSetting.objects.filter(
        singleton_key=1,
        study_access_enabled=True,
    ).exists():
        raise PermissionDenied

    if session.status not in {Session.Status.ISSUED, Session.Status.IN_PROGRESS}:
        raise SessionNotOpen("This session is no longer accepting responses.")
    current = (
        SessionItem.objects.filter(session=session, response__isnull=True)
        .order_by("display_order")
        .first()
    )
    if current is None or current.pk != item.pk:
        raise OutOfOrderResponse("Answer the current question before continuing.")
    try:
        choice = QuestionChoice.objects.get(pk=selected_choice_id, question=item.question)
    except QuestionChoice.DoesNotExist as exc:
        raise InvalidChoice("Select one of the choices for this question.") from exc
    if hint_used and session.session_type != Session.SessionType.FOUNDATIONAL:
        raise HintNotAllowed("Hints are only available for foundational exercises.")

    response = Response.objects.create(
        session_item=item,
        selected_choice=choice,
        hint_used=bool(hint_used),
    )
    if session.session_type != Session.SessionType.POSTTEST:
        process_response(response.pk)

    if SessionItem.objects.filter(session=session, response__isnull=True).exists():
        if session.status == Session.Status.ISSUED:
            session.status = Session.Status.IN_PROGRESS
            session.save(update_fields=["status", "updated_at"])
    else:
        _finalize(session=session)
    return _result(response, session)
