from django.shortcuts import get_object_or_404

from apps.accounts.models import User
from apps.learning.models import Session


def sessions_visible_to(actor):
    sessions = Session.objects.all()
    if actor.role == User.Role.ADMIN:
        return sessions
    if actor.role == User.Role.TEACHER:
        return sessions.filter(
            student__class_memberships__left_at__isnull=True,
            student__class_memberships__classroom__teacher=actor,
        ).distinct()
    return sessions.filter(student=actor)


def get_scoped_session_or_404(*, actor, session_id):
    return get_object_or_404(sessions_visible_to(actor), pk=session_id)
