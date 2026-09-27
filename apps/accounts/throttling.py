import uuid
from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from django.utils.crypto import salted_hmac

from apps.core.models import AuditEvent
from apps.core.services.audit import record_audit_event


FAILURE_ACTIONS = ("auth.login_failed", "auth.login_throttled")


def _privacy_hash(value, purpose):
    normalized = (value or "").strip().casefold()
    return salted_hmac(f"pathgen.{purpose}", normalized).hexdigest()


def login_subject(identifier, source):
    subject_hash = _privacy_hash(identifier, "login_identifier")
    source_hash = _privacy_hash(source, "login_source")
    target_id = uuid.uuid5(
        uuid.NAMESPACE_URL,
        f"pathgen-login:{subject_hash}:{source_hash}",
    )
    return subject_hash, source_hash, target_id


def get_login_throttle(identifier, source, *, now=None):
    now = now or timezone.now()
    subject_hash, source_hash, target_id = login_subject(identifier, source)
    window_start = now - timedelta(seconds=settings.LOGIN_THROTTLE_WINDOW_SECONDS)
    failure_count = AuditEvent.objects.filter(
        action__in=FAILURE_ACTIONS,
        created_at__gte=window_start,
        metadata_json__subject_hash=subject_hash,
        metadata_json__source_hash=source_hash,
    ).count()

    if failure_count < settings.LOGIN_THROTTLE_MAX_FAILURES:
        return {
            "blocked": False,
            "failure_count": failure_count,
            "retry_after": 0,
            "subject_hash": subject_hash,
            "source_hash": source_hash,
            "target_id": target_id,
        }

    exponent = failure_count - settings.LOGIN_THROTTLE_MAX_FAILURES + 1
    retry_after = min(
        settings.LOGIN_THROTTLE_MAX_DELAY_SECONDS,
        2**exponent,
    )
    return {
        "blocked": True,
        "failure_count": failure_count,
        "retry_after": retry_after,
        "subject_hash": subject_hash,
        "source_hash": source_hash,
        "target_id": target_id,
    }


def record_login_failure(identifier, source, *, throttled=False, retry_after=0):
    subject_hash, source_hash, target_id = login_subject(identifier, source)
    return record_audit_event(
        action="auth.login_throttled" if throttled else "auth.login_failed",
        target_type="accounts.User",
        target_id=target_id,
        metadata={
            "subject_hash": subject_hash,
            "source_hash": source_hash,
            "retry_after": retry_after,
        },
    )
