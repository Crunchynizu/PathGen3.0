import logging
from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.models import User
from apps.accounts.permissions import role_required
from apps.adaptive.bkt import mastery_band
from apps.adaptive.models import SkillMastery
from apps.adaptive.selectors import decisions_for_students, follow_up_targets_for_students
from apps.classrooms.models import Classroom, StudentMembership
from apps.core import metrics
from apps.core.dashboard_data import (
    BAND_LABELS,
    bkt_chart,
    decisions_chart,
    display_name,
    duration_chart,
    matched_gain_chart,
    rag_chart,
    session_result_rows,
    student_dashboard_data,
)
from apps.core.forms import OverrideForm
from apps.core.models import AuditEvent
from apps.core.selectors import (
    current_membership_for_student,
    dashboard_classrooms,
    get_scoped_student_or_404,
    parse_dashboard_filters,
    scoped_dashboard_students,
    selected_dashboard_classroom,
)
from apps.core.services.settings import (
    StaleSettingsRevision,
    current_system_setting,
    update_system_setting,
)
from apps.curriculum.selectors import published_lessons
from apps.learning.models import Session, StudentPath


logger = logging.getLogger(__name__)


def _setting_context(*, form=None, conflict=False):
    setting = current_system_setting()
    return {
        "setting": setting,
        "revision": setting.revision if setting else 0,
        "override_form": form,
        "conflict": conflict,
    }


def _follow_up_rows(students, *, date_from=None, date_to=None, limit=20):
    rows = []
    seen = set()
    for target in follow_up_targets_for_students(
        students,
        date_from=date_from,
        date_to=date_to,
    ):
        key = (target.decision.session.student_id, target.skill_id)
        if key in seen:
            continue
        seen.add(key)
        if target.current_p_known is None:
            band = "Not enough evidence"
        else:
            band = BAND_LABELS[mastery_band(target.current_p_known)]
        rows.append(
            {
                "student": target.decision.session.student,
                "student_name": display_name(target.decision.session.student),
                "skill": target.skill,
                "band": band,
                "lesson": target.decision.session.lesson,
                "created_at": target.decision.created_at,
            }
        )
        if len(rows) == limit:
            break
    student_ids = {row["student"].pk for row in rows}
    if not student_ids:
        return rows
    stages = dict(
        StudentPath.objects.filter(student_id__in=student_ids).values_list(
            "student_id", "current_stage"
        )
    )
    stage_labels = dict(StudentPath.Stage.choices)
    latest_actions = {}
    for decision in decisions_for_students(
        students, date_from=date_from, date_to=date_to
    ).filter(session__student_id__in=student_ids).order_by("-created_at"):
        latest_actions.setdefault(decision.session.student_id, decision.get_action_display())
        if len(latest_actions) == len(student_ids):
            break
    last_activity = dict(
        Session.objects.filter(student_id__in=student_ids)
        .annotate(
            activity_at=Coalesce(
                "completed_at", "submitted_at", "started_at", "created_at"
            )
        )
        .order_by("student_id", "-activity_at")
        .distinct("student_id")
        .values_list("student_id", "activity_at")
    )
    for row in rows:
        student_id = row["student"].pk
        row["latest_action"] = latest_actions.get(student_id)
        row["current_stage"] = stage_labels.get(stages.get(student_id))
        row["last_activity"] = last_activity.get(student_id)
    return rows


@role_required(User.Role.ADMIN)
@never_cache
@require_GET
def admin_dashboard(request):
    filters = parse_dashboard_filters(request.GET)
    classrooms = dashboard_classrooms(request.user)
    selected_class = None
    if not filters.errors:
        selected_class = selected_dashboard_classroom(request.user, filters)
        students = scoped_dashboard_students(request.user, classroom=selected_class)
    else:
        students = User.objects.none()
    cohort = (
        f"Current members of {selected_class.code} · {selected_class.name}"
        if selected_class
        else "All students"
    )
    metric_kwargs = {
        "students": students,
        "cohort": cohort,
        "date_from": filters.date_from,
        "date_to": filters.date_to,
    }
    metric_sources = {
        "active": (metrics.active_students, "Active student accounts in the selected cohort."),
        "completed": (metrics.completed_paths, "Students whose learning path is complete."),
        "matched_sample": (metrics.matched_prepost_sample, "Distinct students with both completed tests."),
        "follow_up": (metrics.follow_up_needed, "Students with persisted follow-up targets."),
        "gain": (metrics.matched_gain, "Mean scores for students with matched pre/post tests."),
        "mastery": (metrics.bkt_mastery_bands, "Evidence-bearing BKT skill bands."),
        "decision": (metrics.q_learning_decisions, "Persisted decisions grouped by lesson and action."),
        "duration": (metrics.median_elapsed_duration, "Median elapsed session time by stage."),
        "rag": (metrics.rag_reliability, "Generated and fallback feedback row counts."),
    }
    metric_results = {}
    for name, (calculate, definition) in metric_sources.items():
        try:
            metric_results[name] = calculate(**metric_kwargs)
        except Exception:
            logger.exception("Admin dashboard metric unavailable: %s", name)
            metric_results[name] = {
                "value": None,
                "cohort": cohort,
                "n": None,
                "definition": definition,
                "window": "Selected date range",
                "version": metrics.METRICS_VERSION,
                "insufficient": True,
                "failed": True,
            }
    active_metric = metric_results["active"]
    completed_metric = metric_results["completed"]
    matched_sample_metric = metric_results["matched_sample"]
    follow_up_metric = metric_results["follow_up"]
    gain_metric = metric_results["gain"]
    mastery_metric = metric_results["mastery"]
    decision_metric = metric_results["decision"]
    duration_metric = metric_results["duration"]
    rag_metric = metric_results["rag"]
    charts = [
        matched_gain_chart(gain_metric),
        bkt_chart(mastery_metric),
        decisions_chart(decision_metric),
        duration_chart(duration_metric),
        rag_chart(rag_metric),
    ]
    gain_series = gain_metric.get("series", {})
    gain_labels = ["Pre-test average", "Post-test average"]
    charts[0]["metric"] = {
        **gain_metric,
        "definition": "Mean pre-test and post-test score percentages for the same students; matched gain is post-test minus pre-test.",
    }
    charts[0]["aria_label"] = (
        f"Bar chart comparing mean pre-test and post-test score percentages "
        f"for matched students in {cohort}."
    )
    if gain_series:
        charts[0]["rows"] = [
            [label, f"{gain_series[label]:.1f}%"] for label in gain_labels
        ]
        charts[0]["config"]["data"]["labels"] = gain_labels
        charts[0]["config"]["data"]["datasets"] = [{
            "label": "Mean score percentage",
            "data": [gain_series[label] for label in gain_labels],
        }]
        charts[0]["config"]["options"]["scales"]["y"]["max"] = 100
    skill_names = {}
    lessons = list(published_lessons())
    for lesson in lessons:
        for lesson_skill in lesson.lesson_skills.all():
            skill_names[lesson_skill.skill.code] = lesson_skill.skill.name
    band_data = mastery_metric["value"] or {}
    charts[1]["metric"] = {
        **mastery_metric,
        "definition": "Counts of evidence-bearing student-skill records in Needs Practice, Developing, and Strong bands (MASTERY-BANDS-V1).",
    }
    charts[1]["aria_label"] = (
        f"Stacked bar chart of student counts by skill and BKT band for {cohort}."
    )
    if band_data:
        skill_codes = sorted(skill_names)
        charts[1]["rows"] = [
            [
                code,
                skill_names[code],
                *(
                    [band_data[code][key] for key in ("np", "dev", "strong")]
                    if code in band_data
                    else ["Not enough evidence"] * 3
                ),
            ]
            for code in skill_codes
        ]
        charts[1]["config"]["data"]["labels"] = [
            skill_names[code] for code in skill_codes
        ]
        for dataset, key, label in zip(
            charts[1]["config"]["data"]["datasets"],
            ("np", "dev", "strong"),
            ("Needs Practice", "Developing", "Strong"),
        ):
            dataset["label"] = label
            dataset["data"] = [
                band_data[code][key] if code in band_data else None
                for code in skill_codes
            ]
        charts[1]["headers"] = [
            "Skill", "Name", "Needs Practice", "Developing", "Strong"
        ]
        charts[1]["config"]["options"]["scales"] = {
            "x": {"stacked": True},
            "y": {"stacked": True, "beginAtZero": True},
        }
    decision_data = decision_metric["value"] or {}
    lesson_codes = [lesson.code for lesson in lessons]
    decision_actions = (
        "progress", "additional_exercise", "foundational_exercise"
    )
    decision_n = sum(
        decision_data.get(code, {}).get(action, 0)
        for code in lesson_codes for action in decision_actions
    )
    charts[2]["metric"] = {
        **decision_metric,
        "n": None if decision_metric.get("failed") else decision_n,
        "definition": "Persisted decisions for Lessons 1–3, grouped by selected action; whole-course decisions are excluded.",
    }
    if decision_n:
        charts[2]["rows"] = [
            [
                f"Lesson {lesson.lesson_order}",
                *[decision_data.get(lesson.code, {}).get(action, 0) for action in decision_actions],
            ]
            for lesson in lessons
        ]
        charts[2]["config"]["data"]["labels"] = [
            f"Lesson {lesson.lesson_order}" for lesson in lessons
        ]
        for dataset, action in zip(
            charts[2]["config"]["data"]["datasets"], decision_actions
        ):
            dataset["data"] = [
                decision_data.get(code, {}).get(action, 0) for code in lesson_codes
            ]
    else:
        charts[2]["rows"] = []
        charts[2]["config"]["data"]["labels"] = []
    elapsed_data = duration_metric["value"] or {}
    stages = [
        ("Pre-test", Session.SessionType.PRETEST),
        ("Lesson", None),
        ("Regular", Session.SessionType.REGULAR),
        ("Additional", Session.SessionType.ADDITIONAL),
        ("Foundational", Session.SessionType.FOUNDATIONAL),
        ("Activity", Session.SessionType.ACTIVITY),
        ("Post-test", Session.SessionType.POSTTEST),
    ]
    if elapsed_data:
        type_labels = dict(Session.SessionType.choices)
        charts[3]["rows"] = [
            [label, f"{elapsed_data[type_labels[session_type]]:.1f} minutes"]
            if session_type and type_labels[session_type] in elapsed_data
            else [label, "Unavailable"]
            for label, session_type in stages
        ]
        charts[3]["config"]["data"]["labels"] = [label for label, _ in stages]
        charts[3]["config"]["data"]["datasets"] = [{
            "label": "Elapsed session time (minutes)",
            "data": [
                elapsed_data.get(type_labels[session_type]) if session_type else None
                for _, session_type in stages
            ],
        }]
    for chart, metric in zip(
        charts,
        (gain_metric, mastery_metric, decision_metric, duration_metric, rag_metric),
    ):
        chart["error"] = bool(metric.get("failed"))
    system_student_count = User.objects.filter(role=User.Role.STUDENT).count()
    scoped_student_count = students.count()
    return render(
        request,
        "pages/admin/admin_dashboard.html",
        {
            **_setting_context(),
            "as_of": timezone.now(),
            "filters": filters,
            "classrooms": classrooms,
            "selected_class": selected_class,
            "cohort": cohort,
            "system_has_students": system_student_count > 0,
            "filter_no_match": bool(system_student_count and not scoped_student_count),
            "active_metric": active_metric,
            "completed_metric": completed_metric,
            "matched_sample_metric": matched_sample_metric,
            "follow_up_metric": follow_up_metric,
            "charts": charts,
            "follow_up_rows": _follow_up_rows(
                students,
                date_from=filters.date_from,
                date_to=filters.date_to,
            ),
            "recent_audits": AuditEvent.objects.select_related("actor").order_by(
                "-created_at"
            )[:10],
        },
    )


@login_required
@never_cache
@require_GET
def student_progress(request, student_id):
    if request.user.role not in {User.Role.ADMIN, User.Role.TEACHER}:
        raise Http404
    student = get_scoped_student_or_404(actor=request.user, student_id=student_id)
    data = student_dashboard_data(student)
    return render(
        request,
        "pages/shared/view_student_progress_detail.html",
        {
            "student": student,
            "student_name": display_name(student),
            "membership": current_membership_for_student(student),
            **data,
            "all_results": session_result_rows(student.learning_sessions.all()),
            "breadcrumbs": [
                {
                    "label": "Dashboard",
                    "url": (
                        "/admin/dashboard/"
                        if request.user.role == User.Role.ADMIN
                        else "/teacher/dashboard/"
                    ),
                },
                {"label": display_name(student), "url": None},
            ],
        },
    )


@login_required
@never_cache
@require_GET
def student_list(request):
    if request.user.role != User.Role.ADMIN:
        raise Http404

    all_students = User.objects.filter(role=User.Role.STUDENT)
    total_students = all_students.count()
    query = request.GET.get("q", "").strip()[:150]
    account_status = request.GET.get("status", "").strip()
    if account_status not in {"active", "inactive"}:
        account_status = ""
    path_status = request.GET.get("path", "").strip()
    if path_status not in StudentPath.Status.values:
        path_status = ""

    students = all_students
    if query:
        students = students.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
        )
    if account_status:
        students = students.filter(is_active=account_status == "active")
    if path_status:
        students = students.filter(learning_path__status=path_status)
    students = students.order_by("last_name", "first_name", "username", "pk")
    page_obj = Paginator(students, 25).get_page(request.GET.get("page"))
    page_students = list(page_obj.object_list)
    student_ids = [student.pk for student in page_students]

    memberships = {}
    for membership in (
        StudentMembership.objects.filter(
            student_id__in=student_ids,
            left_at__isnull=True,
            classroom__status=Classroom.Status.ACTIVE,
        )
        .select_related("classroom")
        .order_by("classroom__code")
    ):
        memberships.setdefault(membership.student_id, membership)
    paths = StudentPath.objects.filter(student_id__in=student_ids).in_bulk()
    mastery_values = defaultdict(list)
    for student_id, p_known in SkillMastery.objects.filter(
        student_id__in=student_ids, evidence_count__gt=0
    ).values_list("student_id", "p_known"):
        mastery_values[student_id].append(p_known)
    latest_activity = dict(
        Session.objects.filter(student_id__in=student_ids)
        .annotate(activity_at=Coalesce("completed_at", "submitted_at", "started_at", "created_at"))
        .order_by("student_id", "-activity_at")
        .distinct("student_id")
        .values_list("student_id", "activity_at")
    )
    follow_up_ids = {
        target.decision.session.student_id
        for target in follow_up_targets_for_students(
            User.objects.filter(pk__in=student_ids)
        )
    }
    band_labels = {"np": "Needs Practice", "dev": "Developing", "strong": "Strong"}
    rows = []
    for student in page_students:
        values = mastery_values.get(student.pk, [])
        band = mastery_band(sum(values) / len(values)) if values else None
        rows.append({
            "student": student,
            "name": display_name(student),
            "membership": memberships.get(student.pk),
            "path": paths.get(student.pk),
            "mastery_band": band,
            "mastery_label": band_labels.get(band, "Not enough evidence"),
            "latest_activity": latest_activity.get(student.pk),
            "needs_follow_up": student.pk in follow_up_ids,
            "progress_url": reverse("portal:student_progress", args=[student.pk]),
        })
    return render(request, "pages/admin/student_list.html", {
        "rows": rows,
        "page_obj": page_obj,
        "total_students": total_students,
        "query": query,
        "account_status": account_status,
        "path_status": path_status,
        "path_choices": StudentPath.Status.choices,
        "filter_active": bool(query or account_status or path_status),
    })


@role_required(User.Role.ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def override(request):
    if request.method == "GET":
        return render(request, "pages/admin/override.html", _setting_context())

    form = OverrideForm(request.POST)
    if form.is_valid():
        try:
            update_system_setting(actor=request.user, **form.cleaned_data)
        except StaleSettingsRevision:
            form.add_error(None, "Someone else changed this. Please review and try again.")
            return render(
                request,
                "pages/admin/override.html",
                _setting_context(form=form, conflict=True),
                status=409,
            )
        messages.success(request, "Access setting updated.")
        return redirect("portal:override")
    messages.error(request, "Review the access-setting form and try again.")
    return render(
        request,
        "pages/admin/override.html",
        _setting_context(form=form),
        status=400,
    )


@role_required(User.Role.ADMIN)
@never_cache
@require_GET
def audit_logs(request):
    events = AuditEvent.objects.select_related("actor").order_by("-created_at")
    query = request.GET.get("q", "").strip()
    if query:
        events = events.filter(Q(action__icontains=query) | Q(reason__icontains=query))
    page = Paginator(events, 25).get_page(request.GET.get("page"))
    return render(request, "pages/admin/audit_logs.html", {"page_obj": page, "query": query})


@role_required(User.Role.ADMIN, User.Role.TEACHER)
@require_GET
def content_redirect(request):
    return redirect("curriculum:content")
