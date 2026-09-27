from dataclasses import dataclass

from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.accounts.models import User
from apps.adaptive.services import process_response
from apps.core.models import SystemSetting
from apps.curriculum.models import QuestionChoice
from apps.learning.models import Response, Session, SessionItem, StudentPath
from apps.learning.services.finalization import finalize_locked_session


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

REQUIRED_PATH_STATUS = {
    Session.SessionType.PRETEST: StudentPath.Status.PRETEST_REQUIRED,
    Session.SessionType.REGULAR: StudentPath.Status.LEARNING,
    Session.SessionType.ADDITIONAL: StudentPath.Status.LEARNING,
    Session.SessionType.FOUNDATIONAL: StudentPath.Status.LEARNING,
    Session.SessionType.ACTIVITY: StudentPath.Status.ACTIVITY_READY,
    Session.SessionType.POSTTEST: StudentPath.Status.POSTTEST_READY,
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


def _validate_path(session, path):
    if (
        path.status != REQUIRED_PATH_STATUS[session.session_type]
        or path.current_stage != session.session_type
    ):
        raise SessionNotOpen("This session no longer matches the learning path.")
    if session.session_type in {
        Session.SessionType.REGULAR,
        Session.SessionType.ADDITIONAL,
        Session.SessionType.FOUNDATIONAL,
    } and path.current_lesson_id != session.lesson_id:
        raise SessionNotOpen("This lesson is no longer the current lesson.")


@transaction.atomic
def submit_response(*, actor, session_id, session_item_id, selected_choice_id, hint_used=False):
    _require_student(actor)
    owner_id = Session.objects.filter(pk=session_id).values_list(
        "student_id",
        flat=True,
    ).get()
    if owner_id != actor.pk:
        raise PermissionDenied
    path = (
        StudentPath.objects.select_for_update(of=("self",))
        .select_related("current_lesson")
        .get(student=actor)
    )
    session = (
        Session.objects.select_for_update(of=("self",))
        .select_related("student", "lesson")
        .get(pk=session_id)
    )

    try:
        item = SessionItem.objects.select_for_update(of=("self",)).select_related(
            "question"
        ).get(
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

    setting = SystemSetting.objects.filter(singleton_key=1).first()
    if setting is None or not setting.study_access_enabled:
        raise PermissionDenied
    if (
        session.session_type == Session.SessionType.POSTTEST
        and not setting.posttest_access_enabled
    ):
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
    _validate_path(session, path)

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
        finalize_locked_session(session=session, path=path)
    return _result(response, session)
