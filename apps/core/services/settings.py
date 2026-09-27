import uuid

from django.core.exceptions import PermissionDenied
from django.db import connection, transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.core.models import SystemSetting
from apps.core.services.audit import record_audit_event


SETTING_LOCK_ID = 4_704_001
SETTING_AUDIT_ID = uuid.uuid5(uuid.NAMESPACE_URL, "pathgen:core-system-setting:1")
SETTING_FIELDS = {
    "study_access": "study_access_enabled",
    "posttest_access": "posttest_access_enabled",
}


class StaleSettingsRevision(Exception):
    def __init__(self, current_revision):
        self.current_revision = current_revision
        super().__init__("The access settings changed. Reload and try again.")


def current_system_setting():
    return SystemSetting.objects.select_related("changed_by").filter(singleton_key=1).first()


@transaction.atomic
def update_system_setting(*, actor, setting_name, enabled, expected_revision, reason):
    if not actor.is_active or actor.role != User.Role.ADMIN:
        raise PermissionDenied
    if setting_name not in SETTING_FIELDS:
        raise ValueError("Unknown setting.")
    reason = reason.strip()
    if not reason:
        raise ValueError("A reason is required.")

    with connection.cursor() as cursor:
        cursor.execute("SELECT pg_advisory_xact_lock(%s)", [SETTING_LOCK_ID])

    setting = (
        SystemSetting.objects.select_for_update()
        .select_related("changed_by")
        .filter(singleton_key=1)
        .first()
    )
    current_revision = setting.revision if setting else 0
    if expected_revision != current_revision:
        raise StaleSettingsRevision(current_revision)

    field_name = SETTING_FIELDS[setting_name]
    before = {
        "study_access_enabled": setting.study_access_enabled if setting else False,
        "posttest_access_enabled": setting.posttest_access_enabled if setting else False,
        "revision": current_revision,
    }
    values = {
        "study_access_enabled": before["study_access_enabled"],
        "posttest_access_enabled": before["posttest_access_enabled"],
    }
    values[field_name] = enabled

    if setting is None:
        setting = SystemSetting.objects.create(
            singleton_key=1,
            changed_by=actor,
            changed_at=timezone.now(),
            revision=1,
            **values,
        )
    else:
        setting.study_access_enabled = values["study_access_enabled"]
        setting.posttest_access_enabled = values["posttest_access_enabled"]
        setting.changed_by = actor
        setting.changed_at = timezone.now()
        setting.revision += 1
        setting.save(
            update_fields=[
                "study_access_enabled",
                "posttest_access_enabled",
                "changed_by",
                "changed_at",
                "revision",
            ]
        )

    record_audit_event(
        action=f"system_setting.{setting_name}.{'enabled' if enabled else 'disabled'}",
        actor=actor,
        target_type="core.SystemSetting",
        target_id=SETTING_AUDIT_ID,
        target_snapshot={
            "study_access_enabled": setting.study_access_enabled,
            "posttest_access_enabled": setting.posttest_access_enabled,
            "revision": setting.revision,
        },
        reason=reason,
        metadata={"before": before},
    )
    return setting
