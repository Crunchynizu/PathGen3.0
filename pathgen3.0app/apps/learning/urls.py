from django.urls import path

from apps.learning import views


app_name = "learning"

urlpatterns = [
    path("student/lessons/<slug:slug>/", views.lesson, name="lesson"),
    path("student/lessons/<slug:slug>/complete/", views.complete_lesson, name="complete_lesson"),
    path("assessment/pretest/", views.pretest_overview, name="pretest_overview"),
    path("assessment/activity/", views.activity_overview, name="activity_overview"),
    path("assessment/posttest/", views.posttest_overview, name="posttest_overview"),
    path(
        "assessment/exercise/<str:session_type>/<slug:slug>/",
        views.exercise_overview,
        name="exercise_overview",
    ),
    path("assessment/session/<uuid:session_id>/", views.assessment_session, name="assessment_session"),
    path(
        "assessment/session/<uuid:session_id>/respond/",
        views.submit_assessment_response,
        name="submit_response",
    ),
    path(
        "assessment/session/<uuid:session_id>/result/",
        views.assessment_result,
        name="assessment_result",
    ),
    path("content_source/transcripts/<str:video_code>.txt", views.transcript, name="transcript"),
]
