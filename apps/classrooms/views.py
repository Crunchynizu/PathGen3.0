from django.contrib import messages
from django.core.exceptions import ValidationError
from django.db.models import Avg, Prefetch
from django.db.models.functions import Coalesce
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from apps.accounts.models import User
from apps.accounts.permissions import role_required
from apps.adaptive.models import SkillMastery
from apps.adaptive.selectors import decisions_for_students, follow_up_targets_for_students
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
    chart_spec,
    display_name,
)
from apps.core.selectors import (
    dashboard_classrooms,
    parse_dashboard_filters,
    scoped_dashboard_students,
    selected_dashboard_classroom,
)
from apps.adaptive.bkt import mastery_band
from apps.curriculum.models import Skill
from apps.learning.models import Session, StudentPath


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
            {"classrooms": classes, "selected_class": None, "filters": filters},
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
    # Follow-up is a current-class signal, not limited by the research date window.
    follow_up_metric = metrics.follow_up_needed(students=students, cohort=cohort)

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
    labels = [value for value, _label in StudentPath.Status.choices]
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

    member_ids = list(students.values_list("pk", flat=True))
    paths = {
        path.student_id: path
        for path in StudentPath.objects.filter(student_id__in=member_ids)
    }
    latest_activity = dict(
        Session.objects.filter(student_id__in=member_ids)
        .annotate(activity_at=Coalesce("completed_at", "submitted_at", "started_at", "created_at"))
        .order_by("student_id", "-activity_at")
        .distinct("student_id")
        .values_list("student_id", "activity_at")
    )
    average_mastery = {
        row["student_id"]: row["average"]
        for row in SkillMastery.objects.filter(student_id__in=member_ids, evidence_count__gt=0)
        .values("student_id")
        .annotate(average=Avg("p_known"))
    }
    latest_actions = {}
    for decision in decisions_for_students(students).order_by("-created_at"):
        latest_actions.setdefault(decision.session.student_id, decision.get_action_display())

    follow_up_rows = []
    seen = set()
    for target in follow_up_targets_for_students(students):
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
                    ("Needs Practice" if mastery_band(target.current_p_known) == "np" else BAND_LABELS[mastery_band(target.current_p_known)])
                    if target.current_p_known is not None
                    else "Not enough evidence"
                ),
                "latest_action": latest_actions.get(target.decision.session.student_id),
                "current_stage": (
                    paths[target.decision.session.student_id].get_current_stage_display()
                    if target.decision.session.student_id in paths else None
                ),
                "last_activity": latest_activity.get(target.decision.session.student_id),
                "created_at": target.decision.created_at,
            }
        )
    follow_up_ids = {row["student"].pk for row in follow_up_rows}
    roster_filter = request.GET.get("roster", "all").strip().lower()
    if roster_filter not in {"all", "follow-up", "in-progress", "completed"}:
        roster_filter = "all"
    roster = []
    for student in students:
        path = paths.get(student.pk)
        status = path.status if path else None
        has_follow_up = student.pk in follow_up_ids
        if roster_filter == "follow-up" and not has_follow_up:
            continue
        if roster_filter == "in-progress" and status not in {
            StudentPath.Status.LEARNING, StudentPath.Status.ACTIVITY_READY,
            StudentPath.Status.POSTTEST_READY,
        }:
            continue
        if roster_filter == "completed" and status != StudentPath.Status.COMPLETED:
            continue
        mastery = average_mastery.get(student.pk)
        band = mastery_band(mastery) if mastery is not None else None
        roster.append({
            "student": student,
            "student_name": display_name(student),
            "path_state": path.get_status_display() if path else "Not started",
            "mastery_band": ("Needs Practice" if band == "np" else BAND_LABELS[band]) if band else "Not enough evidence",
            "latest_activity": latest_activity.get(student.pk),
            "has_follow_up": has_follow_up,
        })

    mastery_values = mastery_metric["value"] or {}
    skills = list(Skill.objects.order_by("code").values("code", "name"))
    bkt_rows = [
        [skill["name"], mastery_values.get(skill["code"], {}).get("np", 0),
         mastery_values.get(skill["code"], {}).get("dev", 0),
         mastery_values.get(skill["code"], {}).get("strong", 0)]
        for skill in skills
    ] if mastery_metric["n"] else []
    bkt = chart_spec(
        chart_id="bkt-bands", title="BKT distribution", metric=mastery_metric,
        headers=["Skill", "Needs Practice", "Developing", "Strong"], rows=bkt_rows,
        labels=[row[0] for row in bkt_rows],
        datasets=[
            {"label": label, "data": [row[index] for row in bkt_rows], "stack": "bands"}
            for index, label in enumerate(("Needs Practice", "Developing", "Strong"), 1)
        ],
        aria_label=f"Stacked bar chart of BKT bands by skill for {cohort}.",
    )
    bkt["config"]["options"]["scales"]["x"] = {"stacked": True}
    bkt["config"]["options"]["scales"]["y"]["stacked"] = True
    bkt["empty_message"] = "Not enough evidence for BKT bands"

    gain_series = gain_metric.get("series") or {}
    gain_rows = [[label, f"{gain_series[label]:.1f}%"] for label in ("Pre-test average", "Post-test average") if label in gain_series]
    gain = chart_spec(
        chart_id="matched-gain", title="Matched pre/post gain", metric=gain_metric,
        headers=["Assessment", "Mean score"], rows=gain_rows,
        labels=[row[0] for row in gain_rows],
        datasets=[{"label": "Mean score (%)", "data": [gain_series[label] for label, _ in gain_rows]}],
        aria_label=f"Bar chart of paired pre-test and post-test mean scores for {cohort}.",
    )
    gain["empty_message"] = "Not enough matched pre/post data"
    gain["config"]["options"]["scales"]["y"]["max"] = 100

    actions = ("progress", "additional_exercise", "foundational_exercise")
    decisions_by_lesson = decisions_metric["value"] or {}
    lesson_labels = list(decisions_by_lesson)
    decision_rows = [
        [action, *[decisions_by_lesson[lesson].get(action, 0) for lesson in lesson_labels]]
        for action in actions
    ] if decisions_metric["n"] else []
    decisions = chart_spec(
        chart_id="decisions", title="Q-Learning decisions", metric=decisions_metric,
        headers=["Decision action", *lesson_labels], rows=decision_rows,
        labels=list(actions) if decisions_metric["n"] else [],
        datasets=[
            {"label": lesson, "data": [decisions_by_lesson[lesson].get(action, 0) for action in actions]}
            for lesson in lesson_labels
        ],
        aria_label=f"Grouped bar chart of Q-Learning decision actions by lesson for {cohort}.",
    )
    decisions["empty_message"] = "No Q-Learning decisions yet"
    completion_chart["empty_message"] = "No learning paths to chart"
    # Revalidate before rendering in case the assignment changed during this request.
    if not dashboard_classrooms(request.user).filter(pk=selected.pk).exists():
        return redirect("portal:my_classes")
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
            "learning_count": sum(path_counts[state] for state in (
                StudentPath.Status.LEARNING, StudentPath.Status.ACTIVITY_READY,
                StudentPath.Status.POSTTEST_READY,
            )),
            "follow_up_metric": follow_up_metric,
            "follow_up_rows": follow_up_rows,
            "charts": [
                bkt,
                gain,
                decisions,
                completion_chart,
            ],
            "roster": roster,
            "roster_filter": roster_filter,
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
