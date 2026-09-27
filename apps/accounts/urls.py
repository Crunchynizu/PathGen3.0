from django.urls import path

from apps.accounts import views


app_name = "account"

urlpatterns = [
    path("login/", views.login_view, name="login"),
    path("logout/", views.logout_view, name="logout"),
    path("my-account/", views.my_account, name="my_account"),
    path("my-account/name/", views.update_name, name="update_name"),
    path("my-account/password/", views.update_password, name="update_password"),
    path("dashboard/admin/", views.admin_dashboard, name="admin_dashboard"),
    path("dashboard/teacher/", views.teacher_dashboard, name="teacher_dashboard"),
    path("dashboard/student/", views.student_dashboard, name="student_dashboard"),
]
