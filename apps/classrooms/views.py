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
    return render(request, "admin/class_management.html", _class_management_context())


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
        "admin/class_management.html",
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
    classes = Classroom.objects.filter(
        teacher=request.user,
        status=Classroom.Status.ACTIVE,
    ).order_by("code")
    selected = None
    class_id = request.GET.get("class")
    if class_id:
        try:
            selected = get_scoped_classroom_or_404(
                actor=request.user,
                classroom_id=class_id,
            )
        except (ValidationError, ValueError) as exc:
            raise Http404 from exc
    elif classes.exists():
        selected = classes.first()
    roster = (
        selected.student_memberships.filter(left_at__isnull=True)
        .select_related("student")
        .order_by("student__last_name", "student__first_name")
        if selected
        else StudentMembership.objects.none()
    )
    return render(
        request,
        "teacher/teacher_dashboard.html",
        {"classrooms": classes, "selected_class": selected, "roster": roster},
    )


@role_required(User.Role.TEACHER)
@never_cache
@require_GET
def my_classes(request):
    classes = Classroom.objects.filter(
        teacher=request.user,
        status=Classroom.Status.ACTIVE,
    ).order_by("code")
    return render(request, "teacher/my_class.html", {"classrooms": classes})


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
        "teacher/class_detail.html",
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
