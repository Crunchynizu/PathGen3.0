from .base import *  # noqa: F403

DEBUG = True

if not SECRET_KEY:  # noqa: F405
    SECRET_KEY = "pathgen-local-only-insecure-secret-key"

if not ALLOWED_HOSTS:  # noqa: F405
    ALLOWED_HOSTS = ["127.0.0.1", "localhost"]
