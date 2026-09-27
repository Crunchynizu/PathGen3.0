from django.urls import include, path

from apps.accounts.views import home
from apps.core.health import health

urlpatterns = [
    path("", home, name="home"),
    path("account/", include("apps.accounts.urls")),
    path("health/", health, name="health"),
]
