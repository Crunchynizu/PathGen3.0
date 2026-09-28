from __future__ import annotations

from django.db.models import Count, Q
from django.urls import reverse

from apps.adaptive.bkt import mastery_band
from apps.adaptive.models import SkillMastery
from apps.core.services.settings import current_system_setting
from apps.curriculum.models import Lesson, Skill
from apps.feedback.models import SessionFeedback
from apps.learning.models import Session, StudentPath


BAND_LABELS = {
    "np": "Not proficient yet",
    "dev": "Developing",
    "strong": "Strong",
}


def display_name(user):
    full_name = " ".join(part for part in [user.first_name, user.last_name] if part).strip()
    return full_name or user.username


def session_result_rows(sessions, *, limit=None):
    sessions = sessions.filter(
        status=Session.Status.COMPLETED,
        voided_at__isnull=True,
    ).select_related("lesson").annotate(
        total_count=Count("items", distinct=True),
        correct_count=Count(
            "items",
            filter=Q(items__response__selected_choice__is_correct=True),
            distinct=True,
        ),
    ).order_by("-completed_at", "-created_at")
    if limit:
        sessions = sessions[:limit]
    return [
        {
            "id": session.pk,
            "type": session.get_session_type_display(),
            "lesson": session.lesson.code if session.lesson else "Whole course",
            "score": f"{session.correct_count}/{session.total_count}",
            "completed_at": session.completed_at,
        }
        for session in sessions
    ]


def student_skill_rows(student):
    masteries = {
        row.skill_id: row
        for row in SkillMastery.objects.filter(student=student).select_related("skill")
    }
    rows = []
    for skill in Skill.objects.order_by("code"):
        mastery = masteries.get(skill.pk)
        if mastery and mastery.evidence_count > 0:
            band = mastery_band(mastery.p_known)
            label = BAND_LABELS[band]
            state = band
            evidence = f"{mastery.evidence_count} evidence item{'s' if mastery.evidence_count != 1 else ''}"
        else:
            label = "Not enough evidence"
            state = "insufficient"
            evidence = "No scored evidence yet"
        rows.append(
            {
                "code": skill.code,
                "name": skill.name,
                "band": label,
                "state": state,
                "evidence": evidence,
            }
        )
    return rows


def student_lesson_rows(student, path):
    lessons = list(Lesson.objects.filter(is_published=True).order_by("lesson_order"))
    if not lessons:
        return []
    completed_orders = set(
        Session.objects.filter(
            student=student,
            status=Session.Status.COMPLETED,
            voided_at__isnull=True,
            lesson__isnull=False,
        ).values_list("lesson__lesson_order", flat=True)
    )
    after_lessons = bool(
        path
        and path.status
        in [StudentPath.Status.ACTIVITY_READY, StudentPath.Status.POSTTEST_READY, StudentPath.Status.COMPLETED]
    )
    current_order = path.current_lesson.lesson_order if path and path.current_lesson else None
    rows = []
    for lesson in lessons:
        completed = after_lessons or (current_order is not None and lesson.lesson_order < current_order)
        if lesson.lesson_order in completed_orders and (
            current_order is None or lesson.lesson_order != current_order
        ):
            completed = True
        reached = completed or (
            path
            and path.status != StudentPath.Status.PRETEST_REQUIRED
            and current_order is not None
            and lesson.lesson_order <= current_order
        )
        state = "completed" if completed else "reached" if reached else "not_reached"
        rows.append({"lesson": lesson, "state": state, "label": state.replace("_", " ").title()})
    return rows


def next_step_for_path(path):
    if path is None:
        return {
            "label": "Path setup pending",
            "description": "Your learning path is not available yet.",
            "url": None,
        }
    if path.status == StudentPath.Status.PRETEST_REQUIRED:
        return {
            "label": "Begin or resume your pre-test",
            "description": "Complete the pre-test to open your lesson path.",
            "url": reverse("learning:pretest_overview"),
        }
    if path.status == StudentPath.Status.LEARNING:
        if path.current_stage == StudentPath.Stage.LESSON and path.current_lesson:
            return {
                "label": f"Review {path.current_lesson.title}",
                "description": "Read the lesson, then continue to its practice.",
                "url": reverse("learning:lesson", kwargs={"slug": path.current_lesson.slug}),
            }
        if path.current_stage in {
            StudentPath.Stage.REGULAR,
            StudentPath.Stage.ADDITIONAL,
            StudentPath.Stage.FOUNDATIONAL,
        } and path.current_lesson:
            branch = {
                StudentPath.Stage.REGULAR: "Continue regular practice",
                StudentPath.Stage.ADDITIONAL: "Continue additional practice",
                StudentPath.Stage.FOUNDATIONAL: "Continue foundational practice",
            }[path.current_stage]
            return {
                "label": branch,
                "description": f"Your authorized next step is in {path.current_lesson.title}.",
                "url": reverse(
                    "learning:exercise_overview",
                    kwargs={"session_type": path.current_stage, "slug": path.current_lesson.slug},
                ),
            }
    if path.status == StudentPath.Status.ACTIVITY_READY:
        return {
            "label": "Begin the whole-course activity",
            "description": "Apply ideas from all three lessons.",
            "url": reverse("learning:activity_overview"),
        }
    if path.status == StudentPath.Status.POSTTEST_READY:
        setting = current_system_setting()
        if setting and setting.posttest_access_enabled:
            return {
                "label": "Begin your post-test",
                "description": "Post-test access is open and your path is ready.",
                "url": reverse("learning:posttest_overview"),
            }
        return {
            "label": "Wait for post-test access",
            "description": "Your learning path is ready. An admin will open post-test access.",
            "url": None,
        }
    if path.status == StudentPath.Status.COMPLETED:
        return {
            "label": "Review your completion",
            "description": "Your learning path is complete. Review your recent results below.",
            "url": "#recent-results",
        }
    return {
        "label": "Continue your learning path",
        "description": "Open your current lesson to continue.",
        "url": reverse("account:my_lesson"),
    }


def student_dashboard_data(student):
    path = StudentPath.objects.filter(student=student).select_related("current_lesson").first()
    latest_feedback = (
        SessionFeedback.objects.filter(session__student=student)
        .select_related("session", "session__lesson")
        .order_by("-created_at")
        .first()
    )
    return {
        "path": path,
        "next_step": next_step_for_path(path),
        "lesson_rows": student_lesson_rows(student, path),
        "skill_rows": student_skill_rows(student),
        "latest_feedback": latest_feedback,
        "recent_results": session_result_rows(
            Session.objects.filter(student=student),
            limit=6,
        ),
    }


def chart_spec(*, chart_id, title, metric, headers, rows, labels, datasets, aria_label):
    return {
        "id": chart_id,
        "title": title,
        "metric": metric,
        "headers": headers,
        "rows": rows,
        "aria_label": aria_label,
        "config": {
            "type": "bar",
            "data": {"labels": labels, "datasets": datasets},
            "options": {
                "responsive": True,
                "maintainAspectRatio": False,
                "animation": False,
                "plugins": {"legend": {"position": "bottom"}},
                "scales": {"y": {"beginAtZero": True}},
            },
        },
    }


def matched_gain_chart(metric, *, chart_id="matched-gain", title="Matched pre/post gain"):
    series = metric.get("series", {})
    rows = [[label, f"{value:.1f} percentage points"] for label, value in series.items()]
    chart = chart_spec(
        chart_id=chart_id,
        title=title,
        metric=metric,
        headers=["Measure", "Value"],
        rows=rows,
        labels=list(series),
        datasets=[{"label": "Percentage points", "data": list(series.values())}],
        aria_label=f"Bar chart showing {title.lower()} for {metric['cohort']}.",
    )
    chart["empty_message"] = "Not enough matched pre/post data"
    return chart


def bkt_chart(metric, *, chart_id="bkt-bands", title="BKT mastery by skill"):
    value = metric["value"] or {}
    labels = list(value)
    rows = [
        [code, details["name"], details["np"], details["dev"], details["strong"]]
        for code, details in value.items()
    ]
    return chart_spec(
        chart_id=chart_id,
        title=title,
        metric=metric,
        headers=["Skill", "Name", "Not proficient yet", "Developing", "Strong"],
        rows=rows,
        labels=labels,
        datasets=[
            {"label": "Not proficient yet", "data": [value[code]["np"] for code in labels]},
            {"label": "Developing", "data": [value[code]["dev"] for code in labels]},
            {"label": "Strong", "data": [value[code]["strong"] for code in labels]},
        ],
        aria_label=f"Grouped bar chart showing BKT mastery bands by skill for {metric['cohort']}.",
    )


def decisions_chart(metric, *, chart_id="decisions", title="Q-Learning decisions by lesson"):
    value = metric["value"] or {}
    labels = list(value)
    rows = [
        [
            lesson,
            actions.get("progress", 0),
            actions.get("additional_exercise", 0),
            actions.get("foundational_exercise", 0),
        ]
        for lesson, actions in value.items()
    ]
    return chart_spec(
        chart_id=chart_id,
        title=title,
        metric=metric,
        headers=["Lesson", "Progress", "Additional exercise", "Foundational exercise"],
        rows=rows,
        labels=labels,
        datasets=[
            {"label": "Progress", "data": [value[label].get("progress", 0) for label in labels]},
            {"label": "Additional exercise", "data": [value[label].get("additional_exercise", 0) for label in labels]},
            {"label": "Foundational exercise", "data": [value[label].get("foundational_exercise", 0) for label in labels]},
        ],
        aria_label=f"Grouped bar chart showing Q-Learning decisions by lesson for {metric['cohort']}.",
    )


def duration_chart(metric, *, chart_id="elapsed-duration", title="Median elapsed duration by stage"):
    value = metric["value"] or {}
    return chart_spec(
        chart_id=chart_id,
        title=title,
        metric=metric,
        headers=["Stage", "Median elapsed session time"],
        rows=[[stage, f"{minutes:.1f} minutes"] for stage, minutes in value.items()],
        labels=list(value),
        datasets=[{"label": "Minutes", "data": list(value.values())}],
        aria_label=f"Bar chart showing median elapsed session time by stage for {metric['cohort']}.",
    )


def rag_chart(metric, *, chart_id="rag-reliability", title="RAG reliability"):
    value = metric["value"] or {}
    labels = ["Generated", "Fallback"]
    values = [value.get("generated", 0), value.get("fallback", 0)] if value else []
    return chart_spec(
        chart_id=chart_id,
        title=title,
        metric=metric,
        headers=["Feedback outcome", "Count"],
        rows=[[label, count] for label, count in zip(labels, values)],
        labels=labels if value else [],
        datasets=[{"label": "Feedback rows", "data": values}],
        aria_label=f"Bar chart showing generated and fallback feedback counts for {metric['cohort']}.",
    )
