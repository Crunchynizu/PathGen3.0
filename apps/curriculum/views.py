from django.db.models import Count, Q
from django.shortcuts import render
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.accounts.models import User
from apps.accounts.permissions import role_required
from apps.curriculum.models import QuestionSet
from apps.curriculum.selectors import (
    published_content_question_sets,
    published_lessons,
)


def _content_breadcrumbs(current):
    breadcrumbs = [{"label": "Content", "url": reverse("curriculum:content")}]
    if current != "Content":
        breadcrumbs.append({"label": current, "url": None})
    return breadcrumbs


@role_required(User.Role.ADMIN, User.Role.TEACHER)
@require_GET
def content(request):
    counts = {
        row["set_type"]: row["total"]
        for row in QuestionSet.objects.filter(is_published=True)
        .exclude(set_type=QuestionSet.SetType.PREPOST)
        .order_by()
        .values("set_type")
        .annotate(total=Count("items"))
    }
    return render(
        request,
        "pages/shared/content.html",
        {
            "breadcrumbs": _content_breadcrumbs("Content"),
            "lesson_count": published_lessons().count(),
            "visible_question_count": sum(counts.values()),
            "set_counts": counts,
        },
    )


@role_required(User.Role.ADMIN, User.Role.TEACHER)
@require_GET
def view_lessons(request):
    visible_set = Q(
        question_sets__is_published=True,
        question_sets__set_type__in=[
            QuestionSet.SetType.REGULAR,
            QuestionSet.SetType.ADDITIONAL,
            QuestionSet.SetType.FOUNDATIONAL,
            QuestionSet.SetType.ACTIVITY,
        ],
    )
    lessons = published_lessons().annotate(
        question_count=Count(
            "question_sets__items__question", filter=visible_set, distinct=True,
        ),
        video_count=Count(
            "question_sets__items__question__video",
            filter=visible_set & Q(question_sets__items__question__video__isnull=False),
            distinct=True,
        ),
        figure_count=Count(
            "question_sets__items__question",
            filter=visible_set & Q(question_sets__items__question__image_asset__isnull=False),
            distinct=True,
        ),
    )
    return render(
        request,
        "pages/shared/view_lesson.html",
        {
            "breadcrumbs": _content_breadcrumbs("Lessons"),
            "back_url": reverse("curriculum:content"),
            "back_label": "Back to Content",
            "lessons": lessons,
        },
    )


@role_required(User.Role.ADMIN, User.Role.TEACHER)
@require_GET
def view_questions(request):
    question_sets = published_content_question_sets()
    set_type = request.GET.get("type", "").strip()
    allowed_types = {
        QuestionSet.SetType.REGULAR,
        QuestionSet.SetType.ADDITIONAL,
        QuestionSet.SetType.FOUNDATIONAL,
        QuestionSet.SetType.ACTIVITY,
    }
    if set_type in allowed_types:
        question_sets = question_sets.filter(set_type=set_type)
    else:
        set_type = ""
    return render(
        request,
        "pages/shared/view_questions.html",
        {
            "breadcrumbs": _content_breadcrumbs("Questions"),
            "back_url": reverse("curriculum:content"),
            "back_label": "Back to Content",
            "question_sets": question_sets,
            "selected_type": set_type,
            "set_types": [
                (QuestionSet.SetType.REGULAR, "Regular"),
                (QuestionSet.SetType.ADDITIONAL, "Additional"),
                (QuestionSet.SetType.FOUNDATIONAL, "Foundational"),
                (QuestionSet.SetType.ACTIVITY, "Activity"),
            ],
        },
    )
