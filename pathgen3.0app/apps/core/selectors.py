from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from uuid import UUID

from django.http import Http404
from django.shortcuts import get_object_or_404

from apps.accounts.models import User
from apps.classrooms.models import Classroom, StudentMembership
from apps.learning.models import Session


@dataclass(frozen=True)
class DashboardFilters:
    classroom_id: UUID | None
    date_from: date | None
    date_to: date | None
    errors: tuple[str, ...]
    requested_classroom: bool


def parse_dashboard_filters(params):
    errors = []
    classroom_id = None
    raw_classroom = params.get("class", "").strip()
    if raw_classroom:
        try:
            classroom_id = UUID(raw_classroom)
        except (TypeError, ValueError):
            errors.append("Choose a valid class.")

    def parse_date(name, label):
        raw = params.get(name, "").strip()
        if not raw:
            return None
        try:
            return date.fromisoformat(raw)
        except ValueError:
            errors.append(f"Enter a valid {label} date.")
            return None

    date_from = parse_date("from", "start")
    date_to = parse_date("to", "end")
    if date_from and date_to and date_from > date_to:
        errors.append("The start date must be on or before the end date.")
    return DashboardFilters(
        classroom_id=classroom_id,
        date_from=date_from,
        date_to=date_to,
        errors=tuple(errors),
        requested_classroom=bool(raw_classroom),
    )


def dashboard_classrooms(actor):
    if actor.role == User.Role.ADMIN:
        return Classroom.objects.select_related("teacher").order_by("code")
    if actor.role == User.Role.TEACHER:
        return Classroom.objects.filter(
            teacher=actor,
            status=Classroom.Status.ACTIVE,
        ).select_related("teacher").order_by("code")
    raise Http404


def scoped_dashboard_students(actor, *, classroom=None):
    students = User.objects.filter(role=User.Role.STUDENT)
    if actor.role == User.Role.ADMIN:
        if classroom is not None:
            students = students.filter(
                class_memberships__classroom=classroom,
                class_memberships__left_at__isnull=True,
            )
        return students.distinct().order_by("last_name", "first_name", "username")
    if actor.role == User.Role.TEACHER:
        if classroom is None or classroom.teacher_id != actor.pk:
            raise Http404
        return students.filter(
            class_memberships__classroom=classroom,
            class_memberships__left_at__isnull=True,
            class_memberships__classroom__status=Classroom.Status.ACTIVE,
        ).distinct().order_by("last_name", "first_name", "username")
    if actor.role == User.Role.STUDENT:
        return students.filter(pk=actor.pk)
    raise Http404


def selected_dashboard_classroom(actor, filters, *, default_first=False):
    classrooms = dashboard_classrooms(actor)
    if filters.requested_classroom and filters.classroom_id is None:
        return None
    if filters.classroom_id:
        return get_object_or_404(classrooms, pk=filters.classroom_id)
    return classrooms.first() if default_first else None


def get_scoped_student_or_404(*, actor, student_id):
    students = User.objects.filter(role=User.Role.STUDENT)
    if actor.role == User.Role.ADMIN:
        allowed = students
    elif actor.role == User.Role.TEACHER:
        allowed = students.filter(
            class_memberships__left_at__isnull=True,
            class_memberships__classroom__teacher=actor,
            class_memberships__classroom__status=Classroom.Status.ACTIVE,
        ).distinct()
    elif actor.role == User.Role.STUDENT:
        allowed = students.filter(pk=actor.pk)
    else:
        raise Http404
    return get_object_or_404(allowed, pk=student_id)


def sessions_for_students(students, *, date_from=None, date_to=None):
    sessions = Session.objects.filter(student__in=students)
    if date_from:
        sessions = sessions.filter(completed_at__date__gte=date_from)
    if date_to:
        sessions = sessions.filter(completed_at__date__lte=date_to)
    return sessions


def current_membership_for_student(student):
    return (
        StudentMembership.objects.filter(
            student=student,
            left_at__isnull=True,
            classroom__status=Classroom.Status.ACTIVE,
        )
        .select_related("classroom", "classroom__teacher")
        .order_by("classroom__code")
        .first()
    )
