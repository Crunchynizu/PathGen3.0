from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.db.models.deletion import ProtectedError
from django.utils import timezone

from apps.accounts.models import User
from apps.classrooms.models import Classroom, StudentMembership
from apps.core.services.audit import record_audit_event


def _require_admin(actor):
    if not actor.is_active or actor.role != User.Role.ADMIN:
        raise PermissionDenied


def _class_snapshot(classroom):
    return {
        "code": classroom.code,
        "name": classroom.name,
        "status": classroom.status,
        "teacher_id": str(classroom.teacher_id) if classroom.teacher_id else None,
    }


def _valid_teacher(teacher):
    if teacher is not None and (
        not teacher.is_active or teacher.role != User.Role.TEACHER
    ):
        raise ValidationError("Select an active teacher.")


@transaction.atomic
def create_classroom(*, actor, code, name):
    _require_admin(actor)
    classroom = Classroom.objects.create(
        code=code.strip(),
        name=name.strip(),
        status=Classroom.Status.ACTIVE,
    )
    record_audit_event(
        action="classroom.created",
        actor=actor,
        target=classroom,
        target_snapshot=_class_snapshot(classroom),
    )
    return classroom


@transaction.atomic
def update_classroom(*, actor, classroom_id, code, name):
    _require_admin(actor)
    classroom = Classroom.objects.select_for_update().get(pk=classroom_id)
    classroom.code = code.strip()
    classroom.name = name.strip()
    classroom.save(update_fields=["code", "name", "updated_at"])
    record_audit_event(
        action="classroom.updated",
        actor=actor,
        target=classroom,
        target_snapshot=_class_snapshot(classroom),
    )
    return classroom


@transaction.atomic
def assign_teacher(*, actor, classroom_id, teacher):
    _require_admin(actor)
    _valid_teacher(teacher)
    classroom = Classroom.objects.select_for_update().get(pk=classroom_id)
    if classroom.status != Classroom.Status.ACTIVE:
        raise ValidationError("Archived classes cannot be reassigned.")
    previous_teacher_id = classroom.teacher_id
    classroom.teacher = teacher
    classroom.save(update_fields=["teacher", "updated_at"])
    record_audit_event(
        action="classroom.teacher_assigned" if teacher else "classroom.teacher_unassigned",
        actor=actor,
        target=classroom,
        target_snapshot=_class_snapshot(classroom),
        metadata={
            "previous_teacher_id": str(previous_teacher_id) if previous_teacher_id else None
        },
    )
    return classroom


@transaction.atomic
def add_student(*, actor, classroom_id, student):
    _require_admin(actor)
    if not student.is_active or student.role != User.Role.STUDENT:
        raise ValidationError("Select an active student.")
    classroom = Classroom.objects.select_for_update().get(pk=classroom_id)
    if classroom.status != Classroom.Status.ACTIVE:
        raise ValidationError("Students cannot be added to an archived class.")
    if StudentMembership.objects.filter(
        classroom=classroom,
        student=student,
        left_at__isnull=True,
    ).exists():
        raise ValidationError("The student is already in this class.")
    membership = StudentMembership.objects.create(
        classroom=classroom,
        student=student,
        added_by=actor,
    )
    record_audit_event(
        action="classroom.student_added",
        actor=actor,
        target=classroom,
        target_snapshot=_class_snapshot(classroom),
        metadata={"membership_id": str(membership.pk), "student_id": str(student.pk)},
    )
    return membership


@transaction.atomic
def remove_student(*, actor, membership_id):
    _require_admin(actor)
    membership = (
        StudentMembership.objects.select_for_update()
        .select_related("classroom", "student")
        .get(pk=membership_id, left_at__isnull=True)
    )
    membership.left_at = timezone.now()
    membership.removed_by = actor
    membership.save(update_fields=["left_at", "removed_by"])
    record_audit_event(
        action="classroom.student_removed",
        actor=actor,
        target=membership.classroom,
        target_snapshot=_class_snapshot(membership.classroom),
        metadata={
            "membership_id": str(membership.pk),
            "student_id": str(membership.student_id),
        },
    )
    return membership


@transaction.atomic
def archive_classroom(*, actor, classroom_id, reason):
    _require_admin(actor)
    reason = reason.strip()
    if not reason:
        raise ValidationError("A reason is required.")
    classroom = Classroom.objects.select_for_update().get(pk=classroom_id)
    if classroom.status == Classroom.Status.ARCHIVED:
        raise ValidationError("The class is already archived.")
    classroom.status = Classroom.Status.ARCHIVED
    classroom.archived_at = timezone.now()
    classroom.archived_by = actor
    classroom.archive_reason = reason
    classroom.save(
        update_fields=[
            "status",
            "archived_at",
            "archived_by",
            "archive_reason",
            "updated_at",
        ]
    )
    record_audit_event(
        action="classroom.archived",
        actor=actor,
        target=classroom,
        target_snapshot=_class_snapshot(classroom),
        reason=reason,
    )
    return classroom


@transaction.atomic
def reactivate_classroom(*, actor, classroom_id):
    _require_admin(actor)
    classroom = Classroom.objects.select_for_update().get(pk=classroom_id)
    if classroom.status == Classroom.Status.ACTIVE:
        raise ValidationError("The class is already active.")
    classroom.status = Classroom.Status.ACTIVE
    classroom.archived_at = None
    classroom.archived_by = None
    classroom.archive_reason = None
    classroom.save(
        update_fields=[
            "status",
            "archived_at",
            "archived_by",
            "archive_reason",
            "updated_at",
        ]
    )
    record_audit_event(
        action="classroom.reactivated",
        actor=actor,
        target=classroom,
        target_snapshot=_class_snapshot(classroom),
    )
    return classroom


@transaction.atomic
def delete_unused_classroom(*, actor, classroom_id, reason):
    _require_admin(actor)
    reason = reason.strip()
    if not reason:
        raise ValidationError("A reason is required.")
    classroom = Classroom.objects.select_for_update().get(pk=classroom_id)
    if classroom.status != Classroom.Status.ARCHIVED or classroom.teacher_id:
        raise ValidationError("Only archived, unassigned classes can be deleted.")
    if classroom.student_memberships.exists():
        raise ValidationError("This class has membership history and cannot be deleted.")
    snapshot = _class_snapshot(classroom)
    target_id = classroom.pk
    try:
        classroom.delete()
    except ProtectedError as exc:
        raise ValidationError("This class has protected history and cannot be deleted.") from exc
    record_audit_event(
        action="classroom.deleted",
        actor=actor,
        target_type="classrooms.Classroom",
        target_id=target_id,
        target_snapshot=snapshot,
        reason=reason,
    )
