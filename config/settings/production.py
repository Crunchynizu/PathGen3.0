from django.core.exceptions import ImproperlyConfigured

from .base import *  # noqa: F403

required_settings = {
    "SECRET_KEY": SECRET_KEY,  # noqa: F405
    "DATABASE_URL": ENV_DATABASE_URL,  # noqa: F405
    "ALLOWED_HOSTS": ALLOWED_HOSTS,  # noqa: F405
    "CSRF_TRUSTED_ORIGINS": CSRF_TRUSTED_ORIGINS,  # noqa: F405
}
missing_settings = [name for name, value in required_settings.items() if not value]
if missing_settings:
    raise ImproperlyConfigured(
        f"Missing required production settings: {', '.join(missing_settings)}"
    )
if any("*" in host for host in ALLOWED_HOSTS):  # noqa: F405
    raise ImproperlyConfigured("Production ALLOWED_HOSTS cannot contain wildcards.")
if any("*" in origin for origin in CSRF_TRUSTED_ORIGINS):  # noqa: F405
    raise ImproperlyConfigured(
        "Production CSRF_TRUSTED_ORIGINS cannot contain wildcards."
    )

DEBUG = False
SECURE_SSL_REDIRECT = True
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_SAMESITE = "Lax"
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"
    },
}
