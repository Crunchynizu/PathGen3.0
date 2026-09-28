from django.urls import path

from apps.accounts import views as account_views
from apps.classrooms import views as classroom_views
from apps.core import views


app_name = "portal"

urlpatterns = [
    path("admin/dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("admin/users/", account_views.user_management, name="user_management"),
    path("admin/users/create/", account_views.create_managed_user, name="create_user"),
    path("admin/users/<uuid:user_id>/update/", account_views.update_managed_user, name="update_user"),
    path("admin/users/<uuid:user_id>/deactivate/", account_views.deactivate_managed_user, name="deactivate_user"),
    path("admin/users/<uuid:user_id>/reactivate/", account_views.reactivate_managed_user, name="reactivate_user"),
    path("admin/users/<uuid:user_id>/delete/", account_views.delete_managed_user, name="delete_user"),
    path("admin/classes/", classroom_views.class_management, name="class_management"),
    path("admin/classes/create/", classroom_views.create_class, name="create_class"),
    path("admin/classes/<uuid:classroom_id>/update/", classroom_views.update_class, name="update_class"),
    path("admin/classes/<uuid:classroom_id>/teacher/", classroom_views.set_teacher, name="assign_teacher"),
    path("admin/classes/<uuid:classroom_id>/students/add/", classroom_views.add_class_student, name="add_student"),
    path("admin/memberships/<uuid:membership_id>/remove/", classroom_views.remove_class_student, name="remove_student"),
    path("admin/classes/<uuid:classroom_id>/archive/", classroom_views.archive_class, name="archive_class"),
    path("admin/classes/<uuid:classroom_id>/reactivate/", classroom_views.reactivate_class, name="reactivate_class"),
    path("admin/classes/<uuid:classroom_id>/delete/", classroom_views.delete_class, name="delete_class"),
    path("admin/override/", views.override, name="override"),
    path("admin/audit-logs/", views.audit_logs, name="audit_logs"),
    path("teacher/dashboard/", classroom_views.teacher_dashboard, name="teacher_dashboard"),
    path("teacher/classes/", classroom_views.my_classes, name="my_classes"),
    path("teacher/classes/<uuid:classroom_id>/", classroom_views.class_detail, name="class_detail"),
    path("students/<uuid:student_id>/progress/", views.student_progress, name="student_progress"),
    path("content/", views.content_redirect, name="content"),
]
