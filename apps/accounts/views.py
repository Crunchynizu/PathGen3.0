from django.contrib import messages
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.forms import (
    AccountNameForm,
    AccountPasswordChangeForm,
    CreateManagedUserForm,
    LifecycleReasonForm,
    LoginForm,
    UpdateManagedUserForm,
)
from apps.accounts.models import User
from apps.accounts.permissions import role_required
from apps.accounts.services.lifecycle import (
    change_own_password,
    create_account,
    deactivate_account,
    delete_unused_account,
    reactivate_account,
    update_account_profile,
    update_own_name,
)
from apps.accounts.sessions import initialize_security_session
from apps.accounts.throttling import get_login_throttle, record_login_failure
from apps.core.services.audit import record_audit_event


GENERIC_LOGIN_ERROR = "Invalid username or password."


def _request_source(request):
    return request.META.get("REMOTE_ADDR", "unknown")


def _safe_next_url(request):
    candidate = request.POST.get("next") or request.GET.get("next")
    if candidate and url_has_allowed_host_and_scheme(
        candidate,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return candidate
    return None


def dashboard_url_for(user):
    return {
        User.Role.ADMIN: reverse("portal:admin_dashboard"),
        User.Role.TEACHER: reverse("portal:teacher_dashboard"),
        User.Role.STUDENT: reverse("account:student_dashboard"),
    }[user.role]


@require_GET
def home(request):
    if request.user.is_authenticated:
        return redirect(dashboard_url_for(request.user))
    return redirect("account:login")


@never_cache
@require_http_methods(["GET", "POST"])
def login_view(request):
    if request.user.is_authenticated:
        return redirect(dashboard_url_for(request.user))

    next_url = _safe_next_url(request)
    form = LoginForm(request.POST or None)
    status = 200
    if request.method == "POST" and form.is_valid():
        username = form.cleaned_data["username"]
        source = _request_source(request)
        throttle = get_login_throttle(username, source)
        if throttle["blocked"]:
            record_login_failure(
                username,
                source,
                throttled=True,
                retry_after=throttle["retry_after"],
            )
            form.add_error(None, GENERIC_LOGIN_ERROR)
            status = 429
        else:
            user = authenticate(
                request,
                username=username,
                password=form.cleaned_data["password"],
            )
            if user is None:
                record_login_failure(username, source)
                form.add_error(None, GENERIC_LOGIN_ERROR)
            else:
                login(request, user)
                initialize_security_session(request.session)
                record_audit_event(
                    action="auth.login_succeeded",
                    actor=user,
                    target=user,
                    target_snapshot={"role": user.role, "is_active": user.is_active},
                )
                return redirect(next_url or dashboard_url_for(user))

    return render(
        request,
        "account/login.html",
        {"form": form, "next": next_url or ""},
        status=status,
    )


@login_required
@never_cache
@require_http_methods(["GET", "POST"])
def logout_view(request):
    if request.method == "POST":
        user = request.user
        record_audit_event(
            action="auth.logout",
            actor=user,
            target=user,
            target_snapshot={"role": user.role, "is_active": user.is_active},
        )
        logout(request)
        return redirect("account:login")
    return render(request, "modals/auth/logout_confirm.html")


def _account_context(user, *, name_form=None, password_form=None):
    return {
        "name_form": name_form
        or AccountNameForm(
            initial={"first_name": user.first_name, "last_name": user.last_name}
        ),
        "password_form": password_form or AccountPasswordChangeForm(user),
        "breadcrumbs": [
            {"label": "Dashboard", "url": dashboard_url_for(user)},
            {"label": "My Account", "url": None},
        ],
        "back_url": dashboard_url_for(user),
        "back_label": "Back to Dashboard",
    }


@login_required
@never_cache
@require_GET
def my_account(request):
    return render(request, "account/my_account.html", _account_context(request.user))


@login_required
@never_cache
@require_POST
def update_name(request):
    form = AccountNameForm(request.POST)
    if form.is_valid():
        update_own_name(user_id=request.user.pk, **form.cleaned_data)
        messages.success(request, "Your name was updated.")
        return redirect("account:my_account")
    return render(
        request,
        "account/my_account.html",
        _account_context(request.user, name_form=form),
        status=400,
    )


@login_required
@never_cache
@require_POST
def update_password(request):
    form = AccountPasswordChangeForm(request.user, request.POST)
    if form.is_valid():
        user = change_own_password(
            user_id=request.user.pk,
            new_password=form.cleaned_data["new_password1"],
            current_session_key=request.session.session_key,
        )
        update_session_auth_hash(request, user)
        initialize_security_session(request.session)
        messages.success(request, "Your password was changed. Other sessions were signed out.")
        return redirect("account:my_account")
    return render(
        request,
        "account/my_account.html",
        _account_context(request.user, password_form=form),
        status=400,
    )


@role_required(User.Role.ADMIN)
@require_GET
def admin_dashboard(request):
    from apps.core.views import admin_dashboard as portal_dashboard

    return portal_dashboard(request)


@role_required(User.Role.TEACHER)
@require_GET
def teacher_dashboard(request):
    from apps.classrooms.views import teacher_dashboard as portal_dashboard

    return portal_dashboard(request)


@role_required(User.Role.STUDENT)
@require_GET
def student_dashboard(request):
    return HttpResponse("Student dashboard placeholder")


def _managed_user(user_id):
    return get_object_or_404(
        User.objects.filter(role__in=[User.Role.TEACHER, User.Role.STUDENT]),
        pk=user_id,
    )


def _user_management_context(*, create_form=None):
    users = User.objects.filter(
        role__in=[User.Role.TEACHER, User.Role.STUDENT]
    ).order_by("role", "last_name", "first_name", "username")
    return {
        "page_obj": Paginator(users, 25).get_page(1),
        "create_form": create_form or CreateManagedUserForm(),
    }


@role_required(User.Role.ADMIN)
@never_cache
@require_GET
def user_management(request):
    users = User.objects.filter(role__in=[User.Role.TEACHER, User.Role.STUDENT])
    query = request.GET.get("q", "").strip()
    role = request.GET.get("role", "").strip()
    status = request.GET.get("status", "").strip()
    if query:
        users = users.filter(
            Q(username__icontains=query)
            | Q(first_name__icontains=query)
            | Q(last_name__icontains=query)
            | Q(email__icontains=query)
        )
    if role in {User.Role.TEACHER, User.Role.STUDENT}:
        users = users.filter(role=role)
    if status in {"active", "inactive"}:
        users = users.filter(is_active=status == "active")
    users = users.order_by("role", "last_name", "first_name", "username")
    return render(
        request,
        "admin/user_management.html",
        {
            "page_obj": Paginator(users, 25).get_page(request.GET.get("page")),
            "create_form": CreateManagedUserForm(),
            "query": query,
            "selected_role": role,
            "selected_status": status,
        },
    )


@role_required(User.Role.ADMIN)
@require_POST
def create_managed_user(request):
    form = CreateManagedUserForm(request.POST)
    if form.is_valid():
        values = form.cleaned_data.copy()
        values.pop("password_confirm")
        create_account(actor=request.user, **values)
        messages.success(request, "Account created.")
        return redirect("portal:user_management")
    return render(
        request,
        "admin/user_management.html",
        _user_management_context(create_form=form),
        status=400,
    )


@role_required(User.Role.ADMIN)
@require_POST
def update_managed_user(request, user_id):
    user = _managed_user(user_id)
    form = UpdateManagedUserForm(request.POST)
    if form.is_valid():
        update_account_profile(actor=request.user, user_id=user.pk, **form.cleaned_data)
        messages.success(request, "Account details updated.")
    else:
        messages.error(request, "The account details could not be updated.")
    return redirect("portal:user_management")


@role_required(User.Role.ADMIN)
@require_POST
def deactivate_managed_user(request, user_id):
    user = _managed_user(user_id)
    form = LifecycleReasonForm(request.POST)
    if form.is_valid():
        try:
            deactivate_account(
                actor=request.user,
                user_id=user.pk,
                reason=form.cleaned_data["reason"],
            )
        except (ValueError, PermissionDenied) as exc:
            messages.error(request, str(exc) or "The account cannot be deactivated.")
        else:
            messages.success(request, "Account deactivated.")
    else:
        messages.error(request, "A reason is required.")
    return redirect("portal:user_management")


@role_required(User.Role.ADMIN)
@require_POST
def reactivate_managed_user(request, user_id):
    user = _managed_user(user_id)
    try:
        reactivate_account(actor=request.user, user_id=user.pk)
    except (ValueError, PermissionDenied) as exc:
        messages.error(request, str(exc) or "The account cannot be reactivated.")
    else:
        messages.success(request, "Account reactivated.")
    return redirect("portal:user_management")


@role_required(User.Role.ADMIN)
@require_POST
def delete_managed_user(request, user_id):
    user = _managed_user(user_id)
    form = LifecycleReasonForm(request.POST)
    if form.is_valid():
        try:
            delete_unused_account(
                actor=request.user,
                user_id=user.pk,
                reason=form.cleaned_data["reason"],
            )
        except (ValueError, PermissionDenied) as exc:
            messages.error(request, str(exc) or "The account cannot be deleted.")
        else:
            messages.success(request, "Unused account deleted.")
    else:
        messages.error(request, "A reason is required.")
    return redirect("portal:user_management")


@role_required(User.Role.STUDENT)
@require_GET
def my_lesson_placeholder(request):
    from apps.learning.views import my_lesson

    return my_lesson(request)
