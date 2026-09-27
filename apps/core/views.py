from django.contrib import messages
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.models import User
from apps.accounts.permissions import role_required
from apps.classrooms.models import Classroom
from apps.core.forms import OverrideForm
from apps.core.models import AuditEvent
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


@role_required(User.Role.ADMIN)
@never_cache
@require_GET
def admin_dashboard(request):
    return render(
        request,
        "admin/admin_dashboard.html",
        {
            **_setting_context(),
            "active_student_count": User.objects.filter(
                role=User.Role.STUDENT, is_active=True
            ).count(),
            "active_class_count": Classroom.objects.filter(
                status=Classroom.Status.ACTIVE
            ).count(),
            "recent_audits": AuditEvent.objects.select_related("actor").order_by(
                "-created_at"
            )[:5],
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
