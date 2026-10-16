from django.db.models import Count, Prefetch

from apps.curriculum.models import Lesson, QuestionChoice, QuestionSet, QuestionSetItem


def published_lessons():
    return (
        Lesson.objects.filter(is_published=True)
        .prefetch_related("lesson_skills__skill")
        .order_by("lesson_order")
    )


def published_content_question_sets():
    visible_items = QuestionSetItem.objects.select_related(
        "question__skill", "question__video"
    ).prefetch_related(
        Prefetch(
            "question__choices",
            queryset=QuestionChoice.objects.order_by("display_order"),
        )
    ).order_by("display_order")
    return (
        QuestionSet.objects.filter(is_published=True)
        .exclude(set_type=QuestionSet.SetType.PREPOST)
        .select_related("lesson", "skill")
        .annotate(question_count=Count("items"))
        .prefetch_related(Prefetch("items", queryset=visible_items))
        .order_by("set_type", "lesson__lesson_order", "skill__code", "code")
    )
