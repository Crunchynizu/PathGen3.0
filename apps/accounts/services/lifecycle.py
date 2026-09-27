from django.contrib.auth import password_validation
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.sessions import invalidate_user_sessions
from apps.core.services.audit import record_audit_event


def _require_admin(actor):
    if not actor.is_active or actor.role != User.Role.ADMIN:
        raise PermissionDenied


@transaction.atomic
def create_account(*, actor, username, role, password, first_name="", last_name="", email=None):
    _require_admin(actor)
    if role not in {User.Role.TEACHER, User.Role.STUDENT}:
        raise ValueError("Only teacher and student accounts can be created here.")
    user = User(
        username=username.strip(),
        role=role,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        email=User.objects.normalize_email(email) if email else None,
    )
    password_validation.validate_password(password, user=user)
    user.set_password(password)
    user.save()
    record_audit_event(
        action="account.created",
        actor=actor,
        target=user,
        target_snapshot={"role": user.role, "is_active": user.is_active},
    )
    return user


@transaction.atomic
def deactivate_account(*, actor, user_id, reason):
    _require_admin(actor)
    reason = reason.strip()
    if not reason:
        raise ValueError("A deactivation reason is required.")
    user = User.objects.select_for_update().get(pk=user_id)
    if user.role == User.Role.ADMIN:
        raise PermissionDenied
    if not user.is_active:
        raise ValueError("The account is already inactive.")

    user.is_active = False
    user.deactivated_at = timezone.now()
    user.deactivated_by = actor
    user.deactivation_reason = reason
    user.save(
        update_fields=[
            "is_active",
            "deactivated_at",
            "deactivated_by",
            "deactivation_reason",
            "updated_at",
        ]
    )
    invalidated_sessions = invalidate_user_sessions(user.pk)
    record_audit_event(
        action="account.deactivated",
        actor=actor,
        target=user,
        target_snapshot={"role": user.role, "is_active": False},
        reason=reason,
        metadata={"invalidated_sessions": invalidated_sessions},
    )
    return user


@transaction.atomic
def reactivate_account(*, actor, user_id):
    _require_admin(actor)
    user = User.objects.select_for_update().get(pk=user_id)
    if user.role == User.Role.ADMIN:
        raise PermissionDenied
    if user.is_active:
        raise ValueError("The account is already active.")

    user.is_active = True
    user.deactivated_at = None
    user.deactivated_by = None
    user.deactivation_reason = None
    user.save(
        update_fields=[
            "is_active",
            "deactivated_at",
            "deactivated_by",
            "deactivation_reason",
            "updated_at",
        ]
    )
    record_audit_event(
        action="account.reactivated",
        actor=actor,
        target=user,
        target_snapshot={"role": user.role, "is_active": True},
    )
    return user


@transaction.atomic
def update_own_name(*, user_id, first_name, last_name):
    user = User.objects.select_for_update().get(pk=user_id, is_active=True)
    user.first_name = first_name.strip()
    user.last_name = last_name.strip()
    user.save(update_fields=["first_name", "last_name", "updated_at"])
    record_audit_event(
        action="account.name_changed",
        actor=user,
        target=user,
        target_snapshot={"role": user.role, "is_active": user.is_active},
    )
    return user


@transaction.atomic
def change_own_password(*, user_id, new_password, current_session_key):
    user = User.objects.select_for_update().get(pk=user_id, is_active=True)
    password_validation.validate_password(new_password, user=user)
    user.set_password(new_password)
    user.save(update_fields=["password", "updated_at"])
    invalidated_sessions = invalidate_user_sessions(
        user.pk,
        exclude_session_key=current_session_key,
    )
    record_audit_event(
        action="account.password_changed",
        actor=user,
        target=user,
        target_snapshot={"role": user.role, "is_active": user.is_active},
        metadata={"invalidated_sessions": invalidated_sessions},
    )
    return user


@transaction.atomic
def bootstrap_admin(*, username, password, email=None, first_name="", last_name=""):
    password_validation.validate_password(password)
    admin = User.objects.create_superuser(
        username=username.strip(),
        password=password,
        email=User.objects.normalize_email(email) if email else None,
        first_name=first_name.strip(),
        last_name=last_name.strip(),
    )
    record_audit_event(
        action="account.admin_bootstrapped",
        target=admin,
        target_snapshot={"role": admin.role, "is_active": admin.is_active},
    )
    return admin
