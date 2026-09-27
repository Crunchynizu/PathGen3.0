from django.core.exceptions import PermissionDenied
from django.db import transaction

from apps.accounts.models import User
from apps.learning.models import StudentPath


class InvalidPathTransition(ValueError):
    pass


ALLOWED_STATUS_TRANSITIONS = {
    (StudentPath.Status.PRETEST_REQUIRED, StudentPath.Status.LEARNING),
    (StudentPath.Status.LEARNING, StudentPath.Status.LEARNING),
    (StudentPath.Status.LEARNING, StudentPath.Status.ACTIVITY_READY),
    (StudentPath.Status.ACTIVITY_READY, StudentPath.Status.POSTTEST_READY),
    (StudentPath.Status.POSTTEST_READY, StudentPath.Status.COMPLETED),
}


def transition_path(*, path, status, current_stage, current_lesson=None):
    transition = (path.status, status)
    if transition not in ALLOWED_STATUS_TRANSITIONS:
        raise InvalidPathTransition(
            f"Path transition {path.status!r} to {status!r} is not allowed."
        )
    path.status = status
    path.current_stage = current_stage
    path.current_lesson = current_lesson
    path.save(update_fields=["status", "current_stage", "current_lesson", "updated_at"])
    return path


@transaction.atomic
def open_regular_stage(*, actor, lesson):
    if not actor.is_active or actor.role != User.Role.STUDENT:
        raise PermissionDenied
    path = StudentPath.objects.select_for_update().get(student=actor)
    if path.status != StudentPath.Status.LEARNING or path.current_lesson_id != lesson.pk:
        raise InvalidPathTransition("This lesson is not the current lesson.")
    if path.current_stage == StudentPath.Stage.REGULAR:
        return path
    if path.current_stage != StudentPath.Stage.LESSON:
        raise InvalidPathTransition("The regular exercise is not available.")
    return transition_path(
        path=path,
        status=StudentPath.Status.LEARNING,
        current_stage=StudentPath.Stage.REGULAR,
        current_lesson=lesson,
    )
