import uuid

from apps.core.models import AuditEvent


def record_audit_event(
    *,
    action,
    actor=None,
    target=None,
    target_type=None,
    target_id=None,
    target_snapshot=None,
    reason=None,
    metadata=None,
):
    if target is not None:
        target_type = target._meta.label
        target_id = target.pk
    if not target_type:
        raise ValueError("target_type is required.")
    if target_id is None:
        target_id = uuid.UUID(int=0)

    return AuditEvent.objects.create(
        actor=actor,
        action=action,
        target_type=target_type,
        target_id=target_id,
        target_snapshot_json=target_snapshot or {},
        reason=reason,
        metadata_json=metadata or {},
    )
