from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import Http404
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.models import User
from apps.accounts.permissions import role_required
from apps.adaptive.bkt import mastery_band
from apps.adaptive.selectors import follow_up_targets_for_students
from apps.classrooms.models import Classroom
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


def _setting_context(*, form=None, conflict=False):
    setting = current_system_setting()
    return {
        "setting": setting,
        "revision": setting.revision if setting else 0,
        "override_form": form,
        "conflict": conflict,
    }


def _follow_up_rows(students, *, date_from=None, date_to=None, limit=8):
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
    active_metric = metrics.active_students(**metric_kwargs)
    completed_metric = metrics.completed_paths(**metric_kwargs)
    matched_sample_metric = metrics.matched_prepost_sample(**metric_kwargs)
    follow_up_metric = metrics.follow_up_needed(**metric_kwargs)
    gain_metric = metrics.matched_gain(**metric_kwargs)
    mastery_metric = metrics.bkt_mastery_bands(**metric_kwargs)
    decision_metric = metrics.q_learning_decisions(**metric_kwargs)
    duration_metric = metrics.median_elapsed_duration(**metric_kwargs)
    rag_metric = metrics.rag_reliability(**metric_kwargs)
    system_student_count = User.objects.filter(role=User.Role.STUDENT).count()
    scoped_student_count = students.count()
    return render(
        request,
        "admin/admin_dashboard.html",
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
            "charts": [
                matched_gain_chart(gain_metric),
                bkt_chart(mastery_metric),
                decisions_chart(decision_metric),
                duration_chart(duration_metric),
                rag_chart(rag_metric),
            ],
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
        "shared/view_student_progress.html",
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


@role_required(User.Role.ADMIN)
@never_cache
@require_http_methods(["GET", "POST"])
def override(request):
    if request.method == "GET":
        return render(request, "admin/override.html", _setting_context())

    form = OverrideForm(request.POST)
    if form.is_valid():
        try:
            update_system_setting(actor=request.user, **form.cleaned_data)
        except StaleSettingsRevision:
            form.add_error(None, "These settings changed in another request. Review the current state and try again.")
            return render(
                request,
                "admin/override.html",
                _setting_context(form=form, conflict=True),
                status=409,
            )
        messages.success(request, "Access setting updated.")
        return redirect("portal:override")
    messages.error(request, "Review the access-setting form and try again.")
    return render(
        request,
        "admin/override.html",
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
    return render(request, "admin/audit_logs.html", {"page_obj": page, "query": query})


@role_required(User.Role.ADMIN, User.Role.TEACHER)
@require_GET
def content_redirect(request):
    return redirect("curriculum:content")
