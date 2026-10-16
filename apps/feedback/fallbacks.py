from apps.adaptive.models import Decision
from apps.curriculum.models import Lesson


ACTION_PHRASES = {
    Decision.Action.PROGRESS: "continue to the next lesson",
    Decision.Action.ADDITIONAL_EXERCISE: (
        "practice more with additional exercises"
    ),
}


def _has_next_part(lesson):
    if lesson is None or not lesson.part_number:
        return False
    return Lesson.objects.filter(
        is_published=True,
        unit_number=lesson.unit_number,
        part_number__gt=lesson.part_number,
    ).exists()


def _score_label(skill_code, score):
    return f"{skill_code} ({score['correct']}/{score['total']} correct)"


def deterministic_fallback(session, evidence, action):
    scores = evidence["skill_scores"]
    strong = [
        _score_label(skill_code, score)
        for skill_code, score in scores.items()
        if score["total"] and score["correct"] == score["total"]
    ]
    needs_practice = [
        _score_label(skill_code, score)
        for skill_code, score in scores.items()
        if score["correct"] < score["total"]
    ]
    if action == Decision.Action.FOUNDATIONAL_EXERCISE:
        skills = ", ".join(evidence["weak_skills"]) or "the identified skills"
        action_phrase = f"review the foundational practice for {skills}"
    elif action == Decision.Action.PROGRESS and _has_next_part(session.lesson):
        action_phrase = f"continue to the next part of Lesson {session.lesson.unit_number}"
    else:
        action_phrase = ACTION_PHRASES.get(
            action,
            ACTION_PHRASES[Decision.Action.PROGRESS],
        )

    session_label = f"{session.get_session_type_display()} session"
    return (
        f"You completed {session_label}.\n"
        f"Strong: {', '.join(strong) if strong else 'none'}.\n"
        "Needs practice: "
        f"{', '.join(needs_practice) if needs_practice else 'none'}.\n"
        f"Next step: {action_phrase}."
    )
