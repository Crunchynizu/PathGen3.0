import uuid

from django.db import models


PROBABILITY_FIELD = {"max_digits": 7, "decimal_places": 6}


class Skill(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=16, unique=True)
    name = models.CharField(max_length=255)
    description = models.TextField()
    p_l0 = models.DecimalField(**PROBABILITY_FIELD)
    p_t = models.DecimalField(**PROBABILITY_FIELD)
    p_g = models.DecimalField(**PROBABILITY_FIELD)
    p_s = models.DecimalField(**PROBABILITY_FIELD)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "curriculum_skill"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(p_l0__gte=0, p_l0__lte=1),
                name="skill_p_l0_probability",
            ),
            models.CheckConstraint(
                condition=models.Q(p_t__gte=0, p_t__lte=1),
                name="skill_p_t_probability",
            ),
            models.CheckConstraint(
                condition=models.Q(p_g__gte=0, p_g__lte=1),
                name="skill_p_g_probability",
            ),
            models.CheckConstraint(
                condition=models.Q(p_s__gte=0, p_s__lte=1),
                name="skill_p_s_probability",
            ),
        ]


class Lesson(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=16, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    lesson_order = models.PositiveIntegerField(unique=True)
    title = models.CharField(max_length=255)
    summary = models.TextField()
    content_json = models.JSONField()
    content_schema_version = models.PositiveIntegerField()
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "curriculum_lesson"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(lesson_order__gt=0),
                name="lesson_order_positive",
            ),
            models.CheckConstraint(
                condition=models.Q(content_schema_version__gt=0),
                name="lesson_schema_version_positive",
            ),
        ]


class LessonSkill(models.Model):
    pk = models.CompositePrimaryKey("lesson", "skill")
    lesson = models.ForeignKey(
        Lesson,
        on_delete=models.CASCADE,
        related_name="lesson_skills",
    )
    skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        related_name="lesson_skills",
    )
    display_order = models.PositiveSmallIntegerField()

    class Meta:
        db_table = "curriculum_lesson_skill"
        constraints = [
            models.UniqueConstraint(
                fields=["lesson", "display_order"],
                name="unique_lesson_skill_order",
            ),
            models.CheckConstraint(
                condition=models.Q(display_order__in=[1, 2]),
                name="lesson_skill_order_valid",
            ),
        ]


class Video(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True)
    title = models.CharField(max_length=255)
    youtube_video_id = models.CharField(max_length=32, unique=True)
    duration_seconds = models.PositiveIntegerField()
    transcript = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "curriculum_video"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(duration_seconds__gt=0),
                name="video_duration_positive",
            ),
            models.CheckConstraint(
                condition=~models.Q(transcript=""),
                name="video_transcript_nonblank",
            ),
        ]


class Question(models.Model):
    class Difficulty(models.TextChoices):
        STANDARD = "standard", "Standard"
        FOUNDATIONAL = "foundational", "Foundational"

    class PresentationType(models.TextChoices):
        TEXT = "text", "Text"
        FIGURE = "figure", "Figure"
        VIDEO = "video", "Video"

    class CognitiveLevel(models.TextChoices):
        REMEMBER = "remember", "Remember"
        UNDERSTAND = "understand", "Understand"
        APPLY = "apply", "Apply"
        ANALYZE = "analyze", "Analyze"
        EVALUATE = "evaluate", "Evaluate"
        CREATE = "create", "Create"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True)
    skill = models.ForeignKey(
        Skill,
        on_delete=models.PROTECT,
        related_name="questions",
    )
    prompt = models.TextField()
    difficulty = models.CharField(max_length=16, choices=Difficulty.choices)
    presentation_type = models.CharField(
        max_length=16,
        choices=PresentationType.choices,
    )
    cognitive_level = models.CharField(max_length=16, choices=CognitiveLevel.choices)
    solution_steps_json = models.JSONField()
    explanation = models.TextField()
    hint = models.TextField(null=True, blank=True)
    feedback_correct = models.TextField()
    feedback_incorrect = models.TextField()
    image_asset = models.CharField(max_length=255, null=True, blank=True)
    image_alt = models.CharField(max_length=500, null=True, blank=True)
    visual_component = models.CharField(max_length=100, null=True, blank=True)
    visual_config_json = models.JSONField(null=True, blank=True)
    video = models.ForeignKey(
        Video,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="questions",
    )
    video_pause_seconds = models.PositiveIntegerField(null=True, blank=True)
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "curriculum_question"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(difficulty__in=["standard", "foundational"]),
                name="question_difficulty_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(presentation_type__in=["text", "figure", "video"]),
                name="question_presentation_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(
                    cognitive_level__in=[
                        "remember",
                        "understand",
                        "apply",
                        "analyze",
                        "evaluate",
                        "create",
                    ]
                ),
                name="question_cognitive_level_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(hint__isnull=True)
                | models.Q(difficulty="foundational"),
                name="question_hint_foundational_only",
            ),
        ]


class QuestionChoice(models.Model):
    class Label(models.TextChoices):
        A = "A", "A"
        B = "B", "B"
        C = "C", "C"
        D = "D", "D"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    question = models.ForeignKey(
        Question,
        on_delete=models.CASCADE,
        related_name="choices",
    )
    label = models.CharField(max_length=1, choices=Label.choices)
    text = models.TextField()
    is_correct = models.BooleanField(default=False)
    misconception_code = models.CharField(max_length=64, null=True, blank=True)
    display_order = models.PositiveSmallIntegerField()

    class Meta:
        db_table = "curriculum_question_choice"
        constraints = [
            models.UniqueConstraint(
                fields=["question", "label"],
                name="unique_question_choice_label",
            ),
            models.UniqueConstraint(
                fields=["question", "display_order"],
                name="unique_question_choice_order",
            ),
            models.UniqueConstraint(
                fields=["question"],
                condition=models.Q(is_correct=True),
                name="unique_correct_choice_per_question",
            ),
            models.CheckConstraint(
                condition=models.Q(label__in=["A", "B", "C", "D"]),
                name="question_choice_label_valid",
            ),
            models.CheckConstraint(
                condition=models.Q(display_order__range=(1, 4)),
                name="question_choice_order_valid",
            ),
        ]


class QuestionSet(models.Model):
    class SetType(models.TextChoices):
        PREPOST = "prepost", "Pre/Post"
        REGULAR = "regular", "Regular"
        ADDITIONAL = "additional", "Additional"
        FOUNDATIONAL = "foundational", "Foundational"
        ACTIVITY = "activity", "Activity"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField(max_length=64, unique=True)
    name = models.CharField(max_length=255)
    set_type = models.CharField(max_length=16, choices=SetType.choices)
    lesson = models.ForeignKey(
        Lesson,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="question_sets",
    )
    skill = models.ForeignKey(
        Skill,
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="question_sets",
    )
    is_published = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "curriculum_question_set"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(
                    set_type__in=[
                        "prepost",
                        "regular",
                        "additional",
                        "foundational",
                        "activity",
                    ]
                ),
                name="question_set_type_valid",
            ),
            models.CheckConstraint(
                condition=(
                    models.Q(
                        set_type__in=["regular", "additional"],
                        lesson__isnull=False,
                        skill__isnull=True,
                    )
                    | models.Q(
                        set_type="foundational",
                        lesson__isnull=True,
                        skill__isnull=False,
                    )
                    | models.Q(
                        set_type__in=["prepost", "activity"],
                        lesson__isnull=True,
                        skill__isnull=True,
                    )
                ),
                name="question_set_context_valid",
            ),
        ]


class QuestionSetItem(models.Model):
    pk = models.CompositePrimaryKey("question_set", "question")
    question_set = models.ForeignKey(
        QuestionSet,
        on_delete=models.CASCADE,
        related_name="items",
    )
    question = models.ForeignKey(
        Question,
        on_delete=models.PROTECT,
        related_name="set_items",
    )
    display_order = models.PositiveIntegerField()

    class Meta:
        db_table = "curriculum_question_set_item"
        constraints = [
            models.UniqueConstraint(
                fields=["question_set", "display_order"],
                name="unique_question_set_order",
            ),
            models.CheckConstraint(
                condition=models.Q(display_order__gt=0),
                name="question_set_item_order_positive",
            ),
        ]
