from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.utils import timezone

from apps.accounts.sessions import (
    SESSION_LAST_ACTIVITY_KEY,
    SESSION_STARTED_AT_KEY,
    initialize_security_session,
)


class AccountSessionSecurityMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated:
            if not request.user.is_active:
                logout(request)
                return redirect(settings.LOGIN_URL)

            now = timezone.now()
            now_timestamp = int(now.timestamp())
            started_at = request.session.get(SESSION_STARTED_AT_KEY)
            last_activity = request.session.get(SESSION_LAST_ACTIVITY_KEY)
            if started_at is None or last_activity is None:
                initialize_security_session(request.session, now=now)
            elif (
                now_timestamp - started_at
                >= settings.SESSION_ABSOLUTE_TIMEOUT_SECONDS
                or now_timestamp - last_activity
                >= settings.SESSION_IDLE_TIMEOUT_SECONDS
            ):
                logout(request)
                return redirect(settings.LOGIN_URL)
            else:
                request.session[SESSION_LAST_ACTIVITY_KEY] = now_timestamp

        return self.get_response(request)
