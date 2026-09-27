from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

required_settings = {
    "SECRET_KEY": SECRET_KEY,  # noqa: F405
    "DATABASE_URL": ENV_DATABASE_URL,  # noqa: F405
    "ALLOWED_HOSTS": ALLOWED_HOSTS,  # noqa: F405
}
missing_settings = [name for name, value in required_settings.items() if not value]
if missing_settings:
    raise ImproperlyConfigured(
        f"Missing required production settings: {', '.join(missing_settings)}"
    )

DEBUG = False
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}
