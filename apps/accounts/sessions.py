from django.contrib.sessions.models import Session
from django.utils import timezone


SESSION_STARTED_AT_KEY = "pathgen_session_started_at"
SESSION_LAST_ACTIVITY_KEY = "pathgen_session_last_activity"


def initialize_security_session(session, *, now=None):
    timestamp = int((now or timezone.now()).timestamp())
    session[SESSION_STARTED_AT_KEY] = timestamp
    session[SESSION_LAST_ACTIVITY_KEY] = timestamp


def invalidate_user_sessions(user_id, *, exclude_session_key=None):
    session_keys = []
    sessions = Session.objects.filter(expire_date__gte=timezone.now())
    if exclude_session_key:
        sessions = sessions.exclude(session_key=exclude_session_key)

    for session in sessions.iterator():
        session_data = session.get_decoded()
        if str(session_data.get("_auth_user_id")) == str(user_id):
            session_keys.append(session.session_key)

    if session_keys:
        Session.objects.filter(session_key__in=session_keys).delete()
    return len(session_keys)
