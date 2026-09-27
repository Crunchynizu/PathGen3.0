import os

from .base import *  # noqa: F403

DEBUG = False
SECRET_KEY = os.getenv("SECRET_KEY") or "pathgen-test-only-insecure-secret-key"
ALLOWED_HOSTS = ["testserver", "127.0.0.1", "localhost"]
MIDDLEWARE = [
    middleware
    for middleware in MIDDLEWARE  # noqa: F405
    if middleware != "whitenoise.middleware.WhiteNoiseMiddleware"
]

if DATABASES["default"]["ENGINE"] != "django.db.backends.postgresql":  # noqa: F405
    raise RuntimeError("PathGen tests require PostgreSQL.")

DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa: F405
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
