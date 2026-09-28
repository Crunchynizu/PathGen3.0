from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Prefetch
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.models import User
from apps.accounts.permissions import role_required
from apps.adaptive.selectors import follow_up_targets_for_students
from apps.classrooms.forms import (
    AddStudentForm,
    AssignTeacherForm,
    ClassroomForm,
    ReasonForm,
)
from apps.classrooms.models import Classroom, StudentMembership
from apps.classrooms.selectors import get_scoped_classroom_or_404
from apps.classrooms.services import (
    add_student,
    archive_classroom,
    assign_teacher,
    create_classroom,
    delete_unused_classroom,
    reactivate_classroom,
    remove_student,
    update_classroom,
)
from apps.core import metrics
from apps.core.dashboard_data import (
    BAND_LABELS,
    bkt_chart,
    chart_spec,
    decisions_chart,
    display_name,
    matched_gain_chart,
)
from apps.core.selectors import (
    dashboard_classrooms,
    parse_dashboard_filters,
    scoped_dashboard_students,
    selected_dashboard_classroom,
)
from apps.adaptive.bkt import mastery_band
from apps.learning.models import StudentPath


def _admin_classroom(classroom_id):
    return get_object_or_404(Classroom.objects.all(), pk=classroom_id)


def _class_management_context(*, create_form=None):
    current_memberships = StudentMembership.objects.filter(
        left_at__isnull=True
    ).select_related("student")
    classrooms = (
        Classroom.objects.select_related("teacher")
        .prefetch_related(
            Prefetch(
                "student_memberships",
                queryset=current_memberships,
                to_attr="active_memberships",
            )
        )
        .order_by("code")
    )
    return {
        "classrooms": classrooms,
        "create_form": create_form or ClassroomForm(),
        "teachers": User.objects.filter(role=User.Role.TEACHER, is_active=True).order_by(
            "last_name", "first_name", "username"
        ),
        "students": User.objects.filter(role=User.Role.STUDENT, is_active=True).order_by(
            "last_name", "first_name", "username"
        ),
    }


@role_required(User.Role.ADMIN)
@never_cache
@require_GET
def class_management(request):
    return render(request, "pages/admin/class_management.html", _class_management_context())


@role_required(User.Role.ADMIN)
@require_POST
def create_class(request):
    form = ClassroomForm(request.POST)
    if form.is_valid():
        create_classroom(actor=request.user, **form.cleaned_data)
        messages.success(request, "Class created.")
        return redirect("portal:class_management")
    return render(
        request,
        "pages/admin/class_management.html",
        _class_management_context(create_form=form),
        status=400,
    )


@role_required(User.Role.ADMIN)
@require_POST
def update_class(request, classroom_id):
    classroom = _admin_classroom(classroom_id)
    form = ClassroomForm(request.POST, instance=classroom)
    if form.is_valid():
        update_classroom(actor=request.user, classroom_id=classroom.pk, **form.cleaned_data)
        messages.success(request, "Class updated.")
        return redirect("portal:class_management")
    messages.error(request, "The class could not be updated.")
    return redirect("portal:class_management")


@role_required(User.Role.ADMIN)
@require_POST
def set_teacher(request, classroom_id):
    classroom = _admin_classroom(classroom_id)
    form = AssignTeacherForm(request.POST)
    if form.is_valid():
        try:
            assign_teacher(
                actor=request.user,
                classroom_id=classroom.pk,
                teacher=form.cleaned_data["teacher"],
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "Teacher assignment updated.")
    else:
        messages.error(request, "Select a valid teacher.")
    return redirect("portal:class_management")


@role_required(User.Role.ADMIN)
@require_POST
def add_class_student(request, classroom_id):
    classroom = _admin_classroom(classroom_id)
    form = AddStudentForm(request.POST, classroom=classroom)
    if form.is_valid():
        try:
            add_student(
                actor=request.user,
                classroom_id=classroom.pk,
                student=form.cleaned_data["student"],
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "Student added to the class.")
    else:
        messages.error(request, "Select a valid student who is not already in the class.")
    return redirect("portal:class_management")


@role_required(User.Role.ADMIN)
@require_POST
def remove_class_student(request, membership_id):
    get_object_or_404(StudentMembership.objects.filter(left_at__isnull=True), pk=membership_id)
    remove_student(actor=request.user, membership_id=membership_id)
    messages.success(request, "Student removed from the class. Membership history was preserved.")
    return redirect("portal:class_management")


@role_required(User.Role.ADMIN)
@require_POST
def archive_class(request, classroom_id):
    classroom = _admin_classroom(classroom_id)
    form = ReasonForm(request.POST)
    if form.is_valid():
        try:
            archive_classroom(
                actor=request.user,
                classroom_id=classroom.pk,
                reason=form.cleaned_data["reason"],
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "Class archived.")
    else:
        messages.error(request, "A reason is required.")
    return redirect("portal:class_management")


@role_required(User.Role.ADMIN)
@require_POST
def reactivate_class(request, classroom_id):
    classroom = _admin_classroom(classroom_id)
    try:
        reactivate_classroom(actor=request.user, classroom_id=classroom.pk)
    except ValidationError as exc:
        messages.error(request, "; ".join(exc.messages))
    else:
        messages.success(request, "Class reactivated.")
    return redirect("portal:class_management")


@role_required(User.Role.ADMIN)
@require_POST
def delete_class(request, classroom_id):
    classroom = _admin_classroom(classroom_id)
    form = ReasonForm(request.POST)
    if form.is_valid():
        try:
            delete_unused_classroom(
                actor=request.user,
                classroom_id=classroom.pk,
                reason=form.cleaned_data["reason"],
            )
        except ValidationError as exc:
            messages.error(request, "; ".join(exc.messages))
        else:
            messages.success(request, "Unused class deleted.")
    else:
        messages.error(request, "A reason is required.")
    return redirect("portal:class_management")


@role_required(User.Role.TEACHER)
@never_cache
@require_GET
def teacher_dashboard(request):
    filters = parse_dashboard_filters(request.GET)
    if filters.requested_classroom and filters.classroom_id is None:
        raise Http404
    classes = dashboard_classrooms(request.user)
    selected = selected_dashboard_classroom(request.user, filters, default_first=True)
    if selected is None:
        return render(
            request,
            "pages/teacher/teacher_dashboard.html",
            {"classrooms": classes, "selected_class": None},
        )

    students = scoped_dashboard_students(request.user, classroom=selected)
    cohort = f"Current members of {selected.code} · {selected.name}"
    metric_kwargs = {
        "students": students,
        "cohort": cohort,
        "date_from": filters.date_from if not filters.errors else None,
        "date_to": filters.date_to if not filters.errors else None,
    }
    mastery_metric = metrics.bkt_mastery_bands(**metric_kwargs)
    gain_metric = metrics.matched_gain(**metric_kwargs)
    decisions_metric = metrics.q_learning_decisions(**metric_kwargs)
    follow_up_metric = metrics.follow_up_needed(**metric_kwargs)

    path_counts = {value: 0 for value, _label in StudentPath.Status.choices}
    for status in StudentPath.objects.filter(student__in=students).values_list("status", flat=True):
        path_counts[status] += 1
    class_size = students.count()
    completion_metric = {
        "value": path_counts if class_size else None,
        "cohort": cohort,
        "n": class_size,
        "definition": "Current students grouped by their persisted learning-path status.",
        "window": "all-time",
        "version": metrics.METRICS_VERSION,
        "insufficient": class_size == 0,
    }
    labels = [label for _value, label in StudentPath.Status.choices]
    completion_values = [path_counts[value] for value, _label in StudentPath.Status.choices]
    completion_chart = chart_spec(
        chart_id="completion-distribution",
        title="Completion distribution",
        metric=completion_metric,
        headers=["Learning-path status", "Students"],
        rows=list(zip(labels, completion_values)) if class_size else [],
        labels=labels if class_size else [],
        datasets=[{"label": "Students", "data": completion_values if class_size else []}],
        aria_label=f"Bar chart showing learning-path status for {cohort}.",
    )

    follow_up_rows = []
    seen = set()
    for target in follow_up_targets_for_students(
        students,
        date_from=metric_kwargs["date_from"],
        date_to=metric_kwargs["date_to"],
    ):
        key = (target.decision.session.student_id, target.skill_id)
        if key in seen:
            continue
        seen.add(key)
        follow_up_rows.append(
            {
                "student": target.decision.session.student,
                "student_name": display_name(target.decision.session.student),
                "skill": target.skill,
                "band": (
                    BAND_LABELS[mastery_band(target.current_p_known)]
                    if target.current_p_known is not None
                    else "Not enough evidence"
                ),
                "created_at": target.decision.created_at,
            }
        )
        if len(follow_up_rows) == 12:
            break

    roster = selected.student_memberships.filter(left_at__isnull=True).select_related(
        "student", "student__learning_path"
    ).order_by("student__last_name", "student__first_name", "student__username")
    roster_query = request.GET.get("q", "").strip()
    if roster_query:
        roster = roster.filter(
            Q(student__username__icontains=roster_query)
            | Q(student__first_name__icontains=roster_query)
            | Q(student__last_name__icontains=roster_query)
        )
    return render(
        request,
        "pages/teacher/teacher_dashboard.html",
        {
            "classrooms": classes,
            "selected_class": selected,
            "filters": filters,
            "cohort": cohort,
            "class_size": class_size,
            "completed_count": path_counts[StudentPath.Status.COMPLETED],
            "learning_count": path_counts[StudentPath.Status.LEARNING],
            "follow_up_metric": follow_up_metric,
            "follow_up_rows": follow_up_rows,
            "charts": [
                bkt_chart(mastery_metric, title="BKT distribution"),
                matched_gain_chart(gain_metric),
                decisions_chart(decisions_metric, title="Q-Learning decisions"),
                completion_chart,
            ],
            "roster": roster,
            "roster_query": roster_query,
        },
    )


@role_required(User.Role.TEACHER)
@never_cache
@require_GET
def my_classes(request):
    classes = Classroom.objects.filter(
        teacher=request.user,
        status=Classroom.Status.ACTIVE,
    ).order_by("code")
    return render(request, "pages/teacher/my_class.html", {"classrooms": classes})


@role_required(User.Role.TEACHER)
@never_cache
@require_GET
def class_detail(request, classroom_id):
    classroom = get_scoped_classroom_or_404(actor=request.user, classroom_id=classroom_id)
    roster = classroom.student_memberships.filter(left_at__isnull=True).select_related(
        "student"
    ).order_by("student__last_name", "student__first_name")
    return render(
        request,
        "pages/teacher/class_detail.html",
        {
            "classroom": classroom,
            "roster": roster,
            "breadcrumbs": [
                {"label": "My Classes", "url": reverse("portal:my_classes")},
                {"label": classroom.name, "url": None},
            ],
            "back_url": reverse("portal:my_classes"),
            "back_label": "Back to My Classes",
        },
    )
