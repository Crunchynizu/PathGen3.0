import logging
from decimal import Decimal

from django.db import connection, transaction
from django.db.models import Count, Q

from apps.adaptive.bkt import mastery_band, update_mastery_for_session
from apps.adaptive.models import (
    Decision,
    DecisionTargetSkill,
    MasteryEvent,
    SkillMastery,
)
from apps.adaptive.q_learning import (
    POLICY_VERSION,
    decide,
    load_q_table,
    state_key,
)
from apps.curriculum.models import LessonSkill
from apps.learning.models import Response, Session, StudentPath


logger = logging.getLogger(__name__)

REGULAR_ACTIONS = [
    Decision.Action.PROGRESS,
    Decision.Action.ADDITIONAL_EXERCISE,
    Decision.Action.FOUNDATIONAL_EXERCISE,
]
ADDITIONAL_ACTIONS = [
    Decision.Action.PROGRESS,
    Decision.Action.FOUNDATIONAL_EXERCISE,
]
# SCORING-V3: a skill passes with at least two-thirds of its questions correct. A skill has
# 3 questions in a two-skill exercise and in foundational work, 6 in a one-skill Lesson 2 part.
SCORED_SKILL_TOTALS = {3, 6}


def skill_passed(total, correct):
    return total in SCORED_SKILL_TOTALS and correct * 3 >= total * 2


def skill_failed(total, correct):
    return total in SCORED_SKILL_TOTALS and correct * 3 < total * 2


SCORED_SESSION_TYPES = [
    Session.SessionType.REGULAR,
    Session.SessionType.ADDITIONAL,
    Session.SessionType.FOUNDATIONAL,
]


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
    response_ref = (
        Response.objects.select_related(
            "session_item__session",
        )
        .get(pk=response_id)
    )
    session_ref = response_ref.session_item.session
    StudentPath.objects.select_for_update(of=("self",)).filter(
        student_id=session_ref.student_id
    ).first()
    session = Session.objects.select_for_update(of=("self",)).get(
        pk=session_ref.pk
    )
    if session.session_type == Session.SessionType.POSTTEST:
        return None

    response = (
        Response.objects.select_related(
            "selected_choice",
            "session_item__question__skill",
            "session_item__session__student",
        )
        .get(pk=response_id)
    )
    existing_event = MasteryEvent.objects.filter(response=response).first()
    if existing_event is not None:
        return existing_event

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


def _skill_scores(session):
    rows = (
        Response.objects.filter(session_item__session=session)
        .values("session_item__question__skill_id")
        .annotate(
            total=Count("id"),
            correct=Count("id", filter=Q(selected_choice__is_correct=True)),
        )
    )
    return {
        row["session_item__question__skill_id"]: {
            "total": row["total"],
            "correct": row["correct"],
            "passed": skill_passed(row["total"], row["correct"]),
        }
        for row in rows
    }


def _ordered_lesson_skills(session):
    return list(
        LessonSkill.objects.filter(lesson=session.lesson)
        .select_related("skill")
        .order_by("display_order")
    )


def _state_for_session(session, scores):
    # Lessons 1 and 3 have two skills; each Lesson 2 part has one, which gives keys such as
    # "(dev, dev, p)" (weakest = average) in the same Q-table.
    lesson_skills = _ordered_lesson_skills(session)
    if len(lesson_skills) not in (1, 2):
        raise ValueError("Adaptive exercise decisions require one or two lesson skills.")

    masteries = {
        mastery.skill_id: mastery
        for mastery in SkillMastery.objects.filter(
            student=session.student,
            skill_id__in=[row.skill_id for row in lesson_skills],
        )
    }
    if len(masteries) != len(lesson_skills):
        raise ValueError("Adaptive exercise decisions require mastery for every lesson skill.")

    probabilities = [float(masteries[row.skill_id].p_known) for row in lesson_skills]
    weakest_band = mastery_band(min(probabilities))
    average_band = mastery_band(sum(probabilities) / len(probabilities))
    pass_result = "".join(
        "p" if scores.get(row.skill_id, {}).get("passed", False) else "f"
        for row in lesson_skills
    )
    return weakest_band, average_band, pass_result


def _failed_skill_ids(scores):
    return {
        skill_id
        for skill_id, score in scores.items()
        if skill_failed(score["total"], score["correct"])
    }


def _failure_count(*, student_id, skill_id, current_session_id):
    rows = (
        Response.objects.filter(
            session_item__session__student_id=student_id,
            session_item__session__session_type__in=SCORED_SESSION_TYPES,
            session_item__session__voided_at__isnull=True,
            session_item__question__skill_id=skill_id,
        )
        .filter(
            Q(
                session_item__session__status__in=[
                    Session.Status.SUBMITTED,
                    Session.Status.COMPLETED,
                ]
            )
            | Q(session_item__session_id=current_session_id)
        )
        .values("session_item__session_id")
        .annotate(
            total=Count("id"),
            correct=Count("id", filter=Q(selected_choice__is_correct=True)),
        )
    )
    return sum(skill_failed(row["total"], row["correct"]) for row in rows)


def _snapshot(*, state, q_values, chosen_action, available_actions):
    return {
        "state": state,
        "q_values": q_values,
        "chosen_action": chosen_action,
        "available_actions": list(available_actions),
        "policy_version": POLICY_VERSION,
    }


def _create_targets(*, decision, skill_ids, target_kind):
    DecisionTargetSkill.objects.bulk_create(
        [
            DecisionTargetSkill(
                decision=decision,
                skill_id=skill_id,
                target_kind=target_kind,
            )
            for skill_id in sorted(skill_ids, key=str)
        ]
    )


def persist_session_decision(session):
    existing = Decision.objects.filter(session=session).first()
    if existing is not None:
        return existing

    if session.session_type == Session.SessionType.ACTIVITY:
        return Decision.objects.create(
            session=session,
            action=Decision.Action.PROGRESS,
            reason_code="activity_fixed",
            policy_version=POLICY_VERSION,
            input_snapshot_json=_snapshot(
                state=None,
                q_values={},
                chosen_action=Decision.Action.PROGRESS,
                available_actions=[Decision.Action.PROGRESS],
            ),
        )

    scores = _skill_scores(session)
    failed_skill_ids = _failed_skill_ids(scores)

    if session.session_type == Session.SessionType.FOUNDATIONAL:
        action = Decision.Action.PROGRESS
        reason_code = "foundational_fixed"
        state = None
        q_values = {}
        available_actions = [Decision.Action.PROGRESS]
    elif session.session_type in {
        Session.SessionType.REGULAR,
        Session.SessionType.ADDITIONAL,
    }:
        available_actions = (
            REGULAR_ACTIONS
            if session.session_type == Session.SessionType.REGULAR
            else ADDITIONAL_ACTIONS
        )
        try:
            weakest_band, average_band, pass_result = _state_for_session(
                session,
                scores,
            )
            state = state_key(weakest_band, average_band, pass_result)
        except Exception as exc:
            logger.warning(
                "Adaptive state derivation failed; using progress fallback: %s",
                exc,
            )
            action = Decision.Action.PROGRESS
            reason_code = "q_learning_missing_fallback"
            state = None
            q_values = {}
        else:
            action, reason_code = decide(
                weakest_band,
                average_band,
                pass_result,
                available_actions,
            )
            q_values = dict(load_q_table().get(state, {}))
    else:
        raise ValueError("This session type does not receive an adaptive decision.")

    safety_skill_ids = {
        skill_id
        for skill_id in failed_skill_ids
        if _failure_count(
            student_id=session.student_id,
            skill_id=skill_id,
            current_session_id=session.pk,
        )
        >= 3
    }
    if safety_skill_ids:
        action = Decision.Action.PROGRESS
        reason_code = "safety_cap"

    decision = Decision.objects.create(
        session=session,
        action=action,
        reason_code=reason_code,
        policy_version=POLICY_VERSION,
        input_snapshot_json=_snapshot(
            state=state,
            q_values=q_values,
            chosen_action=action,
            available_actions=available_actions,
        ),
    )

    if action in {
        Decision.Action.ADDITIONAL_EXERCISE,
        Decision.Action.FOUNDATIONAL_EXERCISE,
    }:
        _create_targets(
            decision=decision,
            skill_ids=failed_skill_ids,
            target_kind=DecisionTargetSkill.TargetKind.NEXT_EXERCISE,
        )
    elif failed_skill_ids:
        _create_targets(
            decision=decision,
            skill_ids=failed_skill_ids,
            target_kind=DecisionTargetSkill.TargetKind.FOLLOW_UP,
        )
    return decision
