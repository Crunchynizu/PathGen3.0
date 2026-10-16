import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class SystemSetting(models.Model):
    singleton_key = models.PositiveSmallIntegerField(primary_key=True)
    study_access_enabled = models.BooleanField()
    posttest_access_enabled = models.BooleanField()
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="system_setting_changes",
    )
    changed_at = models.DateTimeField(default=timezone.now)
    revision = models.PositiveIntegerField()

    class Meta:
        db_table = "core_system_setting"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(singleton_key=1),
                name="system_setting_singleton_key",
            ),
            models.CheckConstraint(
                condition=models.Q(revision__gte=0),
                name="system_setting_revision_nonnegative",
            ),
        ]


class AuditEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="audit_events",
    )
    action = models.CharField(max_length=100)
    target_type = models.CharField(max_length=100)
    target_id = models.UUIDField()
    target_snapshot_json = models.JSONField()
    reason = models.TextField(null=True, blank=True)
    metadata_json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "core_audit_event"
        indexes = [
            models.Index(fields=["-created_at"], name="core_audit_created_desc_idx"),
        ]
