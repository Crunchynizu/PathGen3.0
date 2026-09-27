import uuid

from django.db import models

from apps.learning.models import Session


class SessionFeedback(models.Model):
    class GenerationStatus(models.TextChoices):
        GENERATED = "generated", "Generated"
        FALLBACK = "fallback", "Fallback"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.OneToOneField(
        Session,
        on_delete=models.PROTECT,
        related_name="feedback",
    )
    feedback_text = models.TextField()
    generation_status = models.CharField(
        max_length=16,
        choices=GenerationStatus.choices,
    )
    model_name = models.CharField(max_length=100, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "feedback_session_feedback"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(generation_status__in=["generated", "fallback"]),
                name="session_feedback_status_valid",
            )
        ]
