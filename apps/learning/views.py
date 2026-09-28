from pathlib import Path

from django.conf import settings
from django.contrib import messages
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.models import User
from apps.accounts.permissions import role_required
from apps.adaptive.models import Decision
from apps.core.models import SystemSetting
from apps.curriculum.models import Lesson, Video
from apps.learning.forms import ResponseForm
from apps.learning.models import Response, Session, SessionItem, StudentPath
from apps.learning.services.paths import InvalidPathTransition, open_regular_stage
from apps.learning.services.responses import (
    HintNotAllowed,
    InvalidChoice,
    OutOfOrderResponse,
    ResponseSubmissionError,
    submit_response,
)
from apps.learning.services.sessions import (
    PosttestLocked,
    QuestionSetInvalid,
    StageMismatch,
    StudyAccessClosed,
    ensure_student_path,
    issue_session,
)


ASSESSMENT_TEMPLATES = {
    Session.SessionType.PRETEST: "assessment/pretest.html",
    Session.SessionType.REGULAR: "assessment/exercise.html",
    Session.SessionType.ADDITIONAL: "assessment/exercise.html",
    Session.SessionType.FOUNDATIONAL: "assessment/exercise.html",
    Session.SessionType.ACTIVITY: "assessment/activity.html",
    Session.SessionType.POSTTEST: "assessment/posttest.html",
}

ASSESSMENT_TITLES = {
    Session.SessionType.PRETEST: "Pre-test",
    Session.SessionType.REGULAR: "Regular exercise",
    Session.SessionType.ADDITIONAL: "Additional exercise",
    Session.SessionType.FOUNDATIONAL: "Foundational exercise",
    Session.SessionType.ACTIVITY: "Course activity",
    Session.SessionType.POSTTEST: "Post-test",
}


def _setting():
    return SystemSetting.objects.filter(singleton_key=1).first()


def _own_session(request, session_id):
    return get_object_or_404(
        Session.objects.select_related("lesson").filter(student=request.user),
        pk=session_id,
    )


def _overview_context(*, request, session_type, lesson=None, locked_reason=None):
    path = ensure_student_path(request.user)
    active = Session.objects.filter(
        student=request.user,
        session_type=session_type,
        lesson=lesson,
        status__in=[Session.Status.ISSUED, Session.Status.IN_PROGRESS],
        voided_at__isnull=True,
    ).first()
    expected = {
        "pretest": 30,
        "regular": 6,
        "additional": 6,
        "activity": 10,
        "posttest": 30,
    }.get(session_type, "3 per assigned skill")
    return {
        "mode": "overview",
        "assessment_title": ASSESSMENT_TITLES[session_type],
        "session_type": session_type,
        "lesson": lesson,
        "path": path,
        "active_session": active,
        "expected_items": expected,
        "locked_reason": locked_reason,
        "dashboard_url": reverse("account:student_dashboard"),
    }


def _assessment_overview(request, *, session_type, lesson=None):
    template = ASSESSMENT_TEMPLATES[session_type]
    setting = _setting()
    locked_reason = None
    if setting is None or not setting.study_access_enabled:
        locked_reason = "Student Study Access is currently closed. Your progress is saved."
    path = ensure_student_path(request.user)
    if path.current_stage != session_type:
        locked_reason = "Complete the current step in My Lesson before starting this assessment."
    if session_type == Session.SessionType.POSTTEST and (
        path.status != StudentPath.Status.POSTTEST_READY
        or setting is None
        or not setting.posttest_access_enabled
    ):
        locked_reason = "The post-test unlocks when the activity is complete and Post-test Access is open."

    if request.method == "POST" and locked_reason is None:
        try:
            session = issue_session(
                actor=request.user,
                session_type=session_type,
                lesson=lesson,
            )
        except (PosttestLocked, StudyAccessClosed, StageMismatch, QuestionSetInvalid) as exc:
            locked_reason = str(exc)
        else:
            return redirect("learning:assessment_session", session_id=session.pk)
    return render(
        request,
        template,
        _overview_context(
            request=request,
            session_type=session_type,
            lesson=lesson,
            locked_reason=locked_reason,
        ),
    )


def _lesson_step_state(*, lesson, path, completed_lesson_ids):
    if lesson.pk in completed_lesson_ids:
        return "completed"
    if path.current_lesson_id == lesson.pk and path.status == StudentPath.Status.LEARNING:
        return "current"
    if path.current_lesson and lesson.lesson_order <= path.current_lesson.lesson_order:
        return "available"
    if path.status in {
        StudentPath.Status.ACTIVITY_READY,
        StudentPath.Status.POSTTEST_READY,
        StudentPath.Status.COMPLETED,
    }:
        return "completed"
    return "locked"


@role_required(User.Role.STUDENT)
@never_cache
@require_GET
def my_lesson(request):
    path = ensure_student_path(request.user)
    lessons = list(Lesson.objects.filter(is_published=True).order_by("lesson_order"))
    completed = set(
        Session.objects.filter(
            student=request.user,
            session_type=Session.SessionType.REGULAR,
            status=Session.Status.COMPLETED,
        ).values_list("lesson_id", flat=True)
    )
    decision_actions = set(
        Decision.objects.filter(session__student=request.user).values_list(
            "session__lesson_id", "action"
        )
    )
    completed_regular_sessions = {
        session.lesson_id: session
        for session in Session.objects.filter(
            student=request.user,
            session_type=Session.SessionType.REGULAR,
            status=Session.Status.COMPLETED,
        ).order_by("lesson__lesson_order", "completed_at")
    }
    lesson_steps = []
    for lesson_obj in lessons:
        state = _lesson_step_state(
            lesson=lesson_obj,
            path=path,
            completed_lesson_ids=completed,
        )
        lesson_steps.append(
            {
                "lesson": lesson_obj,
                "state": state,
                "reached": state != "locked",
                "show_regular": state != "locked",
                "regular_session": completed_regular_sessions.get(lesson_obj.pk),
                "show_additional": (
                    lesson_obj.pk,
                    Decision.Action.ADDITIONAL_EXERCISE,
                ) in decision_actions,
                "show_foundational": (
                    lesson_obj.pk,
                    Decision.Action.FOUNDATIONAL_EXERCISE,
                ) in decision_actions,
            }
        )
    setting = _setting()
    pretest_complete = Session.objects.filter(
        student=request.user,
        session_type=Session.SessionType.PRETEST,
        status=Session.Status.COMPLETED,
    ).exists()
    activity_complete = Session.objects.filter(
        student=request.user,
        session_type=Session.SessionType.ACTIVITY,
        status=Session.Status.COMPLETED,
    ).exists()
    posttest_complete = Session.objects.filter(
        student=request.user,
        session_type=Session.SessionType.POSTTEST,
        status=Session.Status.COMPLETED,
    ).exists()
    pretest_session = Session.objects.filter(
        student=request.user,
        session_type=Session.SessionType.PRETEST,
        status=Session.Status.COMPLETED,
    ).order_by("-completed_at").first()
    activity_session = Session.objects.filter(
        student=request.user,
        session_type=Session.SessionType.ACTIVITY,
        status=Session.Status.COMPLETED,
    ).order_by("-completed_at").first()
    posttest_session = Session.objects.filter(
        student=request.user,
        session_type=Session.SessionType.POSTTEST,
        status=Session.Status.COMPLETED,
    ).order_by("-completed_at").first()
    posttest_available = bool(
        setting
        and setting.posttest_access_enabled
        and path.status == StudentPath.Status.POSTTEST_READY
    )
    return render(
        request,
        "student/my_lesson.html",
        {
            "path": path,
            "lesson_steps": lesson_steps,
            "pretest_state": "completed" if pretest_complete else "current",
            "pretest_session": pretest_session,
            "activity_state": "completed" if activity_complete else (
                "current" if path.current_stage == StudentPath.Stage.ACTIVITY else "locked"
            ),
            "posttest_state": "completed" if posttest_complete else (
                "available" if posttest_available else "locked"
            ),
            "posttest_available": posttest_available,
            "activity_session": activity_session,
            "posttest_session": posttest_session,
            "posttest_locked_reason": (
                "Complete the activity first."
                if path.status not in {StudentPath.Status.POSTTEST_READY, StudentPath.Status.COMPLETED}
                else "Post-test Access is currently closed."
            ),
        },
    )


@role_required(User.Role.STUDENT)
@never_cache
@require_GET
def lesson(request, slug):
    path = ensure_student_path(request.user)
    lesson_obj = get_object_or_404(Lesson.objects.filter(is_published=True), slug=slug)
    reached = path.current_lesson and lesson_obj.lesson_order <= path.current_lesson.lesson_order
    if not reached and path.status not in {
        StudentPath.Status.ACTIVITY_READY,
        StudentPath.Status.POSTTEST_READY,
        StudentPath.Status.COMPLETED,
    }:
        raise Http404
    return render(
        request,
        "student/lesson.html",
        {
            "lesson": lesson_obj,
            "path": path,
            "videos": Video.objects.all().order_by("code"),
            "is_current": path.current_lesson_id == lesson_obj.pk,
            "can_open_regular": (
                path.status == StudentPath.Status.LEARNING
                and path.current_lesson_id == lesson_obj.pk
                and path.current_stage in {StudentPath.Stage.LESSON, StudentPath.Stage.REGULAR}
            ),
            "breadcrumbs": [
                {"label": "My Lesson", "url": reverse("account:my_lesson")},
                {"label": lesson_obj.title, "url": None},
            ],
            "back_url": reverse("account:my_lesson"),
            "back_label": "Back to My Lesson",
        },
    )


@role_required(User.Role.STUDENT)
@require_POST
def complete_lesson(request, slug):
    lesson_obj = get_object_or_404(Lesson.objects.filter(is_published=True), slug=slug)
    try:
        open_regular_stage(actor=request.user, lesson=lesson_obj)
    except InvalidPathTransition as exc:
        messages.error(request, str(exc))
        return redirect("learning:lesson", slug=slug)
    return redirect(
        "learning:exercise_overview",
        session_type=Session.SessionType.REGULAR,
        slug=lesson_obj.slug,
    )


@role_required(User.Role.STUDENT)
@never_cache
@require_http_methods(["GET", "POST"])
def pretest_overview(request):
    return _assessment_overview(request, session_type=Session.SessionType.PRETEST)


@role_required(User.Role.STUDENT)
@never_cache
@require_http_methods(["GET", "POST"])
def activity_overview(request):
    return _assessment_overview(request, session_type=Session.SessionType.ACTIVITY)


@role_required(User.Role.STUDENT)
@never_cache
@require_http_methods(["GET", "POST"])
def posttest_overview(request):
    return _assessment_overview(request, session_type=Session.SessionType.POSTTEST)


@role_required(User.Role.STUDENT)
@never_cache
@require_http_methods(["GET", "POST"])
def exercise_overview(request, session_type, slug):
    allowed = {
        Session.SessionType.REGULAR,
        Session.SessionType.ADDITIONAL,
        Session.SessionType.FOUNDATIONAL,
    }
    if session_type not in allowed:
        raise Http404
    lesson_obj = get_object_or_404(Lesson.objects.filter(is_published=True), slug=slug)
    return _assessment_overview(request, session_type=session_type, lesson=lesson_obj)


def _feedback_context(session, response_id):
    if not response_id or session.session_type not in {
        Session.SessionType.REGULAR,
        Session.SessionType.ADDITIONAL,
        Session.SessionType.FOUNDATIONAL,
        Session.SessionType.ACTIVITY,
    }:
        return None
    response = (
        Response.objects.select_related("selected_choice", "session_item__question")
        .filter(pk=response_id, session_item__session=session)
        .first()
    )
    if response is None:
        return None
    correct = response.selected_choice.is_correct
    question = response.session_item.question
    return {
        "is_correct": correct,
        "heading": "Correct" if correct else "Not quite",
        "text": question.feedback_correct if correct else question.feedback_incorrect,
        "explanation": question.explanation,
    }


@role_required(User.Role.STUDENT)
@never_cache
@require_GET
def assessment_session(request, session_id):
    session = _own_session(request, session_id)
    feedback = _feedback_context(session, request.GET.get("feedback"))
    if session.status == Session.Status.COMPLETED and feedback is None:
        return redirect("learning:assessment_result", session_id=session.pk)
    current = None
    if feedback is None:
        current = (
            SessionItem.objects.select_related("question", "question__video")
            .prefetch_related("question__choices")
            .filter(session=session, response__isnull=True)
            .order_by("display_order")
            .first()
        )
    total = session.items.count()
    context = {
        "mode": "question",
        "assessment_title": ASSESSMENT_TITLES[session.session_type],
        "session": session,
        "session_type": session.session_type,
        "current_item": current,
        "question": current.question if current else None,
        "choices": current.question.choices.order_by("display_order") if current else [],
        "current_number": current.display_order if current else total,
        "total_questions": total,
        "feedback": feedback,
        "next_url": (
            reverse("learning:assessment_result", args=[session.pk])
            if session.status == Session.Status.COMPLETED
            else reverse("learning:assessment_session", args=[session.pk])
        ),
        "exit_url": reverse("account:student_dashboard"),
    }
    return render(request, ASSESSMENT_TEMPLATES[session.session_type], context)


@role_required(User.Role.STUDENT)
@require_POST
def submit_assessment_response(request, session_id):
    session = _own_session(request, session_id)
    form = ResponseForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Select one answer before continuing.")
        return redirect("learning:assessment_session", session_id=session.pk)
    try:
        result = submit_response(
            actor=request.user,
            session_id=session.pk,
            session_item_id=form.cleaned_data["session_item"],
            selected_choice_id=form.cleaned_data["choice"],
            hint_used=form.cleaned_data["hint_used"],
        )
    except (HintNotAllowed, InvalidChoice, OutOfOrderResponse, ResponseSubmissionError) as exc:
        messages.error(request, str(exc))
        return redirect("learning:assessment_session", session_id=session.pk)
    if result.feedback_allowed:
        url = reverse("learning:assessment_session", args=[session.pk])
        return redirect(f"{url}?feedback={result.response.pk}")
    if result.session.status == Session.Status.COMPLETED:
        return redirect("learning:assessment_result", session_id=session.pk)
    return redirect("learning:assessment_session", session_id=session.pk)


@role_required(User.Role.STUDENT)
@never_cache
@require_GET
def assessment_result(request, session_id):
    session = _own_session(request, session_id)
    if session.status != Session.Status.COMPLETED:
        return redirect("learning:assessment_session", session_id=session.pk)
    responses = Response.objects.filter(session_item__session=session)
    score = responses.filter(selected_choice__is_correct=True).count()
    return render(
        request,
        ASSESSMENT_TEMPLATES[session.session_type],
        {
            "mode": "result",
            "assessment_title": ASSESSMENT_TITLES[session.session_type],
            "session": session,
            "session_type": session.session_type,
            "score": score,
            "total_questions": session.items.count(),
            "dashboard_url": reverse("account:student_dashboard"),
            "my_lesson_url": reverse("account:my_lesson"),
        },
    )


@role_required(User.Role.STUDENT)
@require_GET
def transcript(request, video_code):
    if not Video.objects.filter(code=video_code).exists():
        raise Http404
    path = Path(settings.BASE_DIR) / "content_source" / "transcripts" / f"{video_code}.txt"
    if not path.is_file():
        raise Http404
    return FileResponse(path.open("rb"), content_type="text/plain; charset=utf-8")
