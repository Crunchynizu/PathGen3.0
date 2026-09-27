from django.urls import path

from apps.core.health import health

urlpatterns = [
    path("health/", health, name="health"),
]
