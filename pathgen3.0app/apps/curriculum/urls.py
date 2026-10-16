from django.urls import path

from apps.curriculum import views


app_name = "curriculum"

urlpatterns = [
    path("", views.content, name="content"),
    path("lessons/", views.view_lessons, name="view_lessons"),
    path("lessons/<str:code>/", views.view_lesson_detail, name="view_lesson_detail"),
    path("questions/", views.view_questions, name="view_questions"),
]
