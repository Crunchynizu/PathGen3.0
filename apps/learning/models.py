import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.curriculum.models import Lesson, Question, QuestionChoice


class StudentPath(models.Model):
    class Status(models.TextChoices):
        PRETEST_REQUIRED = "pretest_required", "Pre-test required"
        LEARNING = "learning", "Learning"
        ACTIVITY_READY = "activity_ready", "Activity ready"
        POSTTEST_READY = "posttest_ready", "Post-test ready"
        COMPLETED = "completed", "Completed"

    class Stage(models.TextChoices):
        PRETEST = "pretest", "Pre-test"
        LESSON = "lesson", "Lesson"
        REGULAR = "regular", "Regular"
        ADDITIONAL = "additional", "Additional"
        FOUNDATIONAL = "foundational", "Foundational"
        ACTIVITY = "activity", "Activity"
        POSTTEST = "posttest", "Post-test"

    student = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        primary_key=True,
        on_delete=models.PROTECT,
        related_name="learning_path",
    )
    status = models.CharField(max_length=32, choices=Status.choices)
    current_lesson = models.ForeignKey(
        Lesson,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="current_student_paths",
    )
    current_stage = models.CharField(max_length=16, choices=Stage.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "learning_student_path"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    status__in=[
                        "pretest_required",
                        "learning",
                        "activity_ready",
                        "posttest_ready",
                        "completed",
                    ]
                ),
                name="student_path_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    current_stage__in=[
                        "pretest",
                        "lesson",
                        "regular",
                        "additional",
                        "foundational",
                        "activity",
                        "posttest",
                    ]
                ),
                name="student_path_stage_valid",
            ),
        ]


class Session(models.Model):
    class SessionType(models.TextChoices):
        PRETEST = "pretest", "Pre-test"
        REGULAR = "regular", "Regular"
        ADDITIONAL = "additional", "Additional"
        FOUNDATIONAL = "foundational", "Foundational"
        ACTIVITY = "activity", "Activity"
        POSTTEST = "posttest", "Post-test"

    class Status(models.TextChoices):
        ISSUED = "issued", "Issued"
        IN_PROGRESS = "in_progress", "In progress"
        SUBMITTED = "submitted", "Submitted"
        COMPLETED = "completed", "Completed"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="learning_sessions",
    )
    session_type = models.CharField(max_length=16, choices=SessionType.choices)
    lesson = models.ForeignKey(
        Lesson,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="learning_sessions",
    )
    status = models.CharField(max_length=16, choices=Status.choices)
    attempt_number = models.PositiveIntegerField()
    voided_at = models.DateTimeField(null=True, blank=True)
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="voided_learning_sessions",
    )
    void_reason = models.TextField(null=True, blank=True)
    started_at = models.DateTimeField(null=True, blank=True)
    submitted_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "learning_session"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    session_type__in=[
                        "pretest",
                        "regular",
                        "additional",
                        "foundational",
                        "activity",
                        "posttest",
                    ]
                ),
                name="learning_session_type_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    status__in=["issued", "in_progress", "submitted", "completed"]
                ),
                name="learning_session_status_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(attempt_number__gt=0),
                name="learning_session_attempt_positive",
            ),
        ]


class SessionItem(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.ForeignKey(
        Session,
        on_delete=models.PROTECT,
        related_name="items",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.PROTECT,
        related_name="session_items",
    )
    display_order = models.PositiveIntegerField()

    class Meta:
        db_table = "learning_session_item"
        constraints = [
            models.UniqueConstraint(
                fields=["session", "question"],
                name="unique_session_question",
            ),
            models.UniqueConstraint(
                fields=["session", "display_order"],
                name="unique_session_item_order",
            ),
            models.CheckConstraint(
                condition=models.Q(display_order__gt=0),
                name="session_item_order_positive",
            ),
        ]


class Response(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session_item = models.OneToOneField(
        SessionItem,
        on_delete=models.PROTECT,
        related_name="response",
    )
    selected_choice = models.ForeignKey(
        QuestionChoice,
        on_delete=models.PROTECT,
        related_name="responses",
    )
    hint_used = models.BooleanField(default=False)
    answered_at = models.DateTimeField(default=timezone.now)

    class Meta:
        db_table = "learning_response"
