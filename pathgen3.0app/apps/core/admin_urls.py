from django.urls import path

from apps.core import views


app_name = "admin"

urlpatterns = [
    path("students/", views.student_list, name="student_list"),
]
