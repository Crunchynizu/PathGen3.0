import uuid

from django.conf import settings
from django.db import models

from apps.curriculum.models import Skill
from apps.learning.models import Response, Session


PROBABILITY_FIELD = {"max_digits": 7, "decimal_places": 6}


class SkillMastery(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    student = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="skill_masteries",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        related_name="student_masteries",
    )
    p_known = models.DecimalField(**PROBABILITY_FIELD)
    evidence_count = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "adaptive_skill_mastery"
        constraints = [
            models.UniqueConstraint(
                fields=["student", "skill"],
                name="unique_student_skill_mastery",
            ),
            models.CheckConstraint(
                condition=models.Q(p_known__gte=0, p_known__lte=1),
                name="skill_mastery_probability",
            ),
            models.CheckConstraint(
                condition=models.Q(evidence_count__gte=0),
                name="skill_mastery_evidence_nonnegative",
            ),
        ]


class MasteryEvent(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    mastery = models.ForeignKey(
        SkillMastery,
        on_delete=models.PROTECT,
        related_name="events",
    )
    response = models.OneToOneField(
        Response,
        on_delete=models.PROTECT,
        related_name="mastery_event",
    )
    p_before = models.DecimalField(**PROBABILITY_FIELD)
    p_after_observation = models.DecimalField(
        null=True,
        blank=True,
        **PROBABILITY_FIELD,
    )
    p_after_learning = models.DecimalField(**PROBABILITY_FIELD)
    learning_transition_applied = models.BooleanField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "adaptive_mastery_event"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(p_before__gte=0, p_before__lte=1),
                name="mastery_event_p_before_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(p_after_observation__isnull=True)
                | models.Q(p_after_observation__gte=0, p_after_observation__lte=1),
                name="mastery_event_observation_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(p_after_learning__gte=0, p_after_learning__lte=1),
                name="mastery_event_learning_valid",
            ),
        ]


class Decision(models.Model):
    class Action(models.TextChoices):
        PROGRESS = "progress", "Progress"
        ADDITIONAL_EXERCISE = "additional_exercise", "Additional exercise"
        FOUNDATIONAL_EXERCISE = "foundational_exercise", "Foundational exercise"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    session = models.OneToOneField(
        Session,
        on_delete=models.PROTECT,
        related_name="adaptive_decision",
    )
    action = models.CharField(max_length=32, choices=Action.choices)
    reason_code = models.CharField(max_length=64)
    policy_version = models.CharField(max_length=64)
    input_snapshot_json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "adaptive_decision"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    action__in=[
                        "progress",
                        "additional_exercise",
                        "foundational_exercise",
                    ]
                ),
                name="adaptive_decision_action_valid",
            )
        ]


class DecisionTargetSkill(models.Model):
    class TargetKind(models.TextChoices):
        NEXT_EXERCISE = "next_exercise", "Next exercise"
        FOLLOW_UP = "follow_up", "Follow-up"

    pk = models.CompositePrimaryKey("decision", "skill", "target_kind")
    decision = models.ForeignKey(
        Decision,
        on_delete=models.PROTECT,
        related_name="target_skills",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        related_name="decision_targets",
    )
    target_kind = models.CharField(max_length=16, choices=TargetKind.choices)

    class Meta:
        db_table = "adaptive_decision_target_skill"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(target_kind__in=["next_exercise", "follow_up"]),
                name="decision_target_kind_valid",
            )
        ]
