from django.urls import include, path

from apps.accounts.views import home
from apps.core.health import health

urlpatterns = [
    path("", home, name="home"),
    path("account/", include("apps.accounts.urls")),
    path("admin/", include("apps.core.admin_urls")),
    path("content/", include("apps.curriculum.urls")),
    path("", include("apps.learning.urls")),
    path("", include("apps.core.urls")),
    path("health/", health, name="health"),
]

handler400 = "apps.core.errors.bad_request"
handler403 = "apps.core.errors.permission_denied"
handler404 = "apps.core.errors.page_not_found"
handler500 = "apps.core.errors.server_error"
