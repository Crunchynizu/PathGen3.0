from django.db.models import Q
from django.shortcuts import get_object_or_404

from apps.accounts.models import User


def users_visible_to(actor):
    users = User.objects.filter(is_active=True)
    if actor.role == User.Role.ADMIN:
        return users
    if actor.role == User.Role.TEACHER:
        return users.filter(
            Q(pk=actor.pk)
            | Q(
                class_memberships__left_at__isnull=True,
                class_memberships__classroom__teacher=actor,
            )
        ).distinct()
    return users.filter(pk=actor.pk)


def get_scoped_user_or_404(*, actor, user_id):
    return get_object_or_404(users_visible_to(actor), pk=user_id)
