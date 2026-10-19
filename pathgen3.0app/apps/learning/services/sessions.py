from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from apps.accounts.models import User
from apps.adaptive.models import Decision, DecisionTargetSkill
from apps.core.models import SystemSetting
from apps.curriculum.models import QuestionSet, Skill
from apps.learning.models import Session, SessionItem, StudentPath


class SessionIssuanceError(ValueError):
    pass


class StudyAccessClosed(SessionIssuanceError):
    pass


class PosttestLocked(SessionIssuanceError):
    pass


class StageMismatch(SessionIssuanceError):
    pass


class QuestionSetInvalid(SessionIssuanceError):
    pass


SESSION_SET_TYPES = {
    Session.SessionType.PRETEST: QuestionSet.SetType.PREPOST,
    Session.SessionType.POSTTEST: QuestionSet.SetType.PREPOST,
    Session.SessionType.REGULAR: QuestionSet.SetType.REGULAR,
    Session.SessionType.ADDITIONAL: QuestionSet.SetType.ADDITIONAL,
    Session.SessionType.FOUNDATIONAL: QuestionSet.SetType.FOUNDATIONAL,
    Session.SessionType.ACTIVITY: QuestionSet.SetType.ACTIVITY,
}

EXPECTED_COUNTS = {
    Session.SessionType.PRETEST: 30,
    Session.SessionType.POSTTEST: 30,
    Session.SessionType.REGULAR: 6,
    Session.SessionType.ADDITIONAL: 6,
}

REQUIRED_PATH_STATUS = {
    Session.SessionType.PRETEST: StudentPath.Status.PRETEST_REQUIRED,
    Session.SessionType.REGULAR: StudentPath.Status.LEARNING,
    Session.SessionType.ADDITIONAL: StudentPath.Status.LEARNING,
    Session.SessionType.FOUNDATIONAL: StudentPath.Status.LEARNING,
    Session.SessionType.ACTIVITY: StudentPath.Status.ACTIVITY_READY,
    Session.SessionType.POSTTEST: StudentPath.Status.POSTTEST_READY,
}


def ensure_student_path(student):
    if not student.is_active or student.role != User.Role.STUDENT:
        raise PermissionDenied
    path, _ = StudentPath.objects.get_or_create(
        student=student,
        defaults={
            "status": StudentPath.Status.PRETEST_REQUIRED,
            "current_stage": StudentPath.Stage.PRETEST,
        },
    )
    return path


def _require_student(actor):
    if not actor.is_active or actor.role != User.Role.STUDENT:
        raise PermissionDenied


def _system_setting():
    return SystemSetting.objects.filter(singleton_key=1).first()


def _normalize_weak_skills(*, actor, path, weak_skills):
    if weak_skills is not None:
        ids = [getattr(skill, "pk", skill) for skill in weak_skills]
        return list(Skill.objects.filter(pk__in=ids).order_by("code"))

    decision = (
        Decision.objects.filter(
            session__student=actor,
            session__lesson=path.current_lesson,
            action=Decision.Action.FOUNDATIONAL_EXERCISE,
        )
        .order_by("-created_at")
        .first()
    )
    if decision is None:
        return []
    return list(
        Skill.objects.filter(
            decision_targets__decision=decision,
            decision_targets__target_kind=DecisionTargetSkill.TargetKind.NEXT_EXERCISE,
        ).order_by("code")
    )


def _question_rows(*, actor, path, session_type, lesson, weak_skills):
    set_type = SESSION_SET_TYPES[session_type]
    sets = QuestionSet.objects.filter(set_type=set_type, is_published=True)

    if session_type in {Session.SessionType.REGULAR, Session.SessionType.ADDITIONAL}:
        if lesson is None or lesson.pk != path.current_lesson_id:
            raise StageMismatch("The requested lesson is not the current lesson.")
        sets = sets.filter(lesson=lesson, skill__isnull=True)
    elif session_type == Session.SessionType.FOUNDATIONAL:
        if lesson is None or lesson.pk != path.current_lesson_id:
            raise StageMismatch("The requested lesson is not the current lesson.")
        skills = _normalize_weak_skills(
            actor=actor,
            path=path,
            weak_skills=weak_skills,
        )
        if not skills:
            raise QuestionSetInvalid("Foundational work requires at least one weak skill.")
        rows = []
        for skill in skills:
            question_set = sets.filter(skill=skill, lesson__isnull=True).first()
            if question_set is None:
                raise QuestionSetInvalid(f"No published foundational set for {skill.code}.")
            items = list(
                question_set.items.select_related("question")
                .order_by("display_order")
            )
            if len(items) != 3:
                raise QuestionSetInvalid(
                    f"Foundational set {question_set.code} must contain exactly 3 items."
                )
            rows.extend(items)
        return rows
    else:
        sets = sets.filter(lesson__isnull=True, skill__isnull=True)

    question_set = sets.first()
    if question_set is None:
        raise QuestionSetInvalid(f"No published {set_type} question set is available.")
    rows = list(
        question_set.items.select_related("question").order_by("display_order")
    )
    # The activity covers every skill, so its size follows the curriculum.
    expected = EXPECTED_COUNTS.get(session_type)
    if expected is None and not rows:
        raise QuestionSetInvalid(f"Question set {question_set.code} has no items.")
    if expected is not None and len(rows) != expected:
        raise QuestionSetInvalid(
            f"Question set {question_set.code} must contain exactly {expected} items."
        )
    return rows


@transaction.atomic
def issue_session(*, actor, session_type, lesson=None, weak_skills=None):
    _require_student(actor)
    setting = _system_setting()
    if setting is None or not setting.study_access_enabled:
        raise StudyAccessClosed("Student Study Access is currently closed.")

    ensure_student_path(actor)
    path = (
        StudentPath.objects.select_for_update(of=("self",))
        .select_related("current_lesson")
        .get(student=actor)
    )
    if session_type not in Session.SessionType.values:
        raise SessionIssuanceError("Unknown session type.")
    if path.current_stage != session_type:
        raise StageMismatch("This assessment is not the current path stage.")
    if path.status != REQUIRED_PATH_STATUS[session_type]:
        raise StageMismatch("The assessment does not match the current path status.")
    if session_type == Session.SessionType.POSTTEST and (
        not setting.posttest_access_enabled
        or path.status != StudentPath.Status.POSTTEST_READY
    ):
        raise PosttestLocked("The post-test is not available yet.")
    if session_type in {
        Session.SessionType.REGULAR,
        Session.SessionType.ADDITIONAL,
        Session.SessionType.FOUNDATIONAL,
    } and (lesson is None or lesson.pk != path.current_lesson_id):
        raise StageMismatch("The requested lesson is not the current lesson.")

    session_lesson = lesson if session_type in {
        Session.SessionType.REGULAR,
        Session.SessionType.ADDITIONAL,
        Session.SessionType.FOUNDATIONAL,
    } else None
    active = Session.objects.filter(
        student=actor,
        session_type=session_type,
        lesson=session_lesson,
        status__in=[Session.Status.ISSUED, Session.Status.IN_PROGRESS],
        voided_at__isnull=True,
    ).first()
    if active is not None:
        return active

    rows = _question_rows(
        actor=actor,
        path=path,
        session_type=session_type,
        lesson=session_lesson,
        weak_skills=weak_skills,
    )
    previous_attempt = (
        Session.objects.filter(
            student=actor,
            session_type=session_type,
            lesson=session_lesson,
        ).aggregate(value=Max("attempt_number"))["value"]
        or 0
    )
    session = Session.objects.create(
        student=actor,
        session_type=session_type,
        lesson=session_lesson,
        status=Session.Status.ISSUED,
        attempt_number=previous_attempt + 1,
        started_at=timezone.now(),
    )
    SessionItem.objects.bulk_create(
        [
            SessionItem(
                session=session,
                question=row.question,
                display_order=index,
            )
            for index, row in enumerate(rows, start=1)
        ]
    )
    return session
