from django.shortcuts import get_object_or_404

from apps.accounts.models import User
from apps.classrooms.models import Classroom


def classrooms_visible_to(actor):
    classrooms = Classroom.objects.all()
    if actor.role == User.Role.ADMIN:
        return classrooms
    if actor.role == User.Role.TEACHER:
        return classrooms.filter(teacher=actor, status=Classroom.Status.ACTIVE)
    return classrooms.filter(
        status=Classroom.Status.ACTIVE,
        student_memberships__student=actor,
        student_memberships__left_at__isnull=True,
    ).distinct()


def get_scoped_classroom_or_404(*, actor, classroom_id):
    return get_object_or_404(classrooms_visible_to(actor), pk=classroom_id)
