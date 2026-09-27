from decimal import Decimal

from django.db import connection, transaction

from apps.adaptive.bkt import update_mastery_for_session
from apps.adaptive.models import MasteryEvent, SkillMastery
from apps.learning.models import Response, Session


def _decimal_probability(value):
    return Decimal(str(value))


def _lock_mastery_key(*, student_id, skill_id):
    lock_key = f"pathgen:bkt:{student_id}:{skill_id}"
    with connection.cursor() as cursor:
        cursor.execute(
            "SELECT pg_advisory_xact_lock(hashtextextended(%s, 0))",
            [lock_key],
        )


@transaction.atomic(savepoint=False)
def process_response(response_id):
    response = (
        Response.objects.select_related(
            "selected_choice",
            "session_item__question__skill",
            "session_item__session__student",
        )
        .get(pk=response_id)
    )
    session = response.session_item.session
    if session.session_type == Session.SessionType.POSTTEST:
        return None

    student = session.student
    skill = response.session_item.question.skill
    _lock_mastery_key(student_id=student.pk, skill_id=skill.pk)
    mastery = (
        SkillMastery.objects.select_for_update()
        .filter(student=student, skill=skill)
        .first()
    )
    if mastery is None:
        mastery = SkillMastery.objects.create(
            student=student,
            skill=skill,
            p_known=skill.p_l0,
            evidence_count=0,
        )

    existing_event = MasteryEvent.objects.filter(response=response).first()
    if existing_event is not None:
        return existing_event

    p_before = mastery.p_known
    result = update_mastery_for_session(
        p_before,
        response.selected_choice.is_correct,
        skill.p_t,
        skill.p_g,
        skill.p_s,
        session_type=session.session_type,
        hint_used=response.hint_used,
    )
    event = MasteryEvent.objects.create(
        mastery=mastery,
        response=response,
        p_before=p_before,
        p_after_observation=(
            None
            if result.p_after_observation is None
            else _decimal_probability(result.p_after_observation)
        ),
        p_after_learning=_decimal_probability(result.p_after_learning),
        learning_transition_applied=result.learning_transition_applied,
    )
    mastery.p_known = _decimal_probability(result.p_after_learning)
    mastery.evidence_count += 1
    mastery.save(update_fields=["p_known", "evidence_count", "updated_at"])
    return event
