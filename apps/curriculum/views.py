from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.http import Http404
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from apps.accounts.models import User
from apps.accounts.permissions import role_required
from apps.curriculum.models import QuestionSet, Video
from apps.curriculum.selectors import (
    published_content_question_sets,
    published_lessons,
)
from apps.learning.views import _presented_video


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
            # lessons as students see them (Lesson 2's three parts count once)
            "lesson_count": published_lessons().values("unit_number").distinct().count(),
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


@login_required
@require_GET
def view_lesson_detail(request, code):
    if request.user.role not in {User.Role.ADMIN, User.Role.TEACHER}:
        raise Http404
    lesson = get_object_or_404(published_lessons(), code=code)
    skill_ids = [relation.skill_id for relation in lesson.lesson_skills.all()]
    blocks = [dict(block) for block in lesson.content_json.get("blocks", [])]
    video_codes = {block.get("video_code") for block in blocks if block.get("type") == "video"}
    videos = {
        video.code: _presented_video(video)
        for video in Video.objects.filter(code__in=video_codes)
    }
    for block in blocks:
        if block.get("type") == "video":
            block["video"] = videos.get(block.get("video_code"))
    question_sets = list(
        published_content_question_sets().filter(
            Q(lesson=lesson, set_type__in=[
                QuestionSet.SetType.REGULAR, QuestionSet.SetType.ADDITIONAL,
            ])
            | Q(skill_id__in=skill_ids, set_type=QuestionSet.SetType.FOUNDATIONAL)
        ).distinct()
    )
    return render(request, "pages/shared/view_lesson.detail.html", {
        "lesson": lesson,
        "lesson_count": published_lessons().count(),
        "blocks": blocks,
        "question_sets": question_sets,
        "question_total": sum(question_set.question_count for question_set in question_sets),
        "previous_lesson": published_lessons().filter(lesson_order__lt=lesson.lesson_order).last(),
        "next_lesson": published_lessons().filter(lesson_order__gt=lesson.lesson_order).first(),
        "breadcrumbs": [
            {"label": "Content", "url": reverse("curriculum:content")},
            {"label": "Lessons", "url": reverse("curriculum:view_lessons")},
            {"label": lesson.display_label, "url": None},
        ],
    })


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
