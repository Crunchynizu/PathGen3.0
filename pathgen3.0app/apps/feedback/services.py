import logging
import re
from dataclasses import dataclass

from django.db.models import Count, Q

from apps.adaptive.models import Decision
from apps.curriculum.models import QuestionChoice, QuestionSet
from apps.feedback.fallbacks import deterministic_fallback
from apps.feedback.models import SessionFeedback
from apps.feedback.prompts import assemble_prompt
from apps.feedback.providers.groq import GroqFeedbackClient
from apps.feedback.providers.embeddings import get_embedding_client
from apps.feedback.retrieval.similarity import retrieve
from apps.learning.models import Response


logger = logging.getLogger(__name__)
MAX_OUTPUT_WORDS = 180
FORBIDDEN_TERMS = ("api key", "secret", "token", "password", "system prompt")
PROGRESS_PHRASES = ("move on", "next lesson", "continue to the next lesson")
ADDITIONAL_PHRASES = (
    "additional exercise",
    "additional practice",
    "practice more",
)
FOUNDATIONAL_PHRASES = (
    "foundational exercise",
    "foundational practice",
    "review the foundation",
)


@dataclass(frozen=True)
class FeedbackDraft:
    feedback_text: str
    generation_status: str
    model_name: str | None


def session_evidence(session):
    rows = (
        Response.objects.filter(session_item__session=session)
        .values("session_item__question__skill__code")
        .annotate(
            total=Count("id"),
            correct=Count("id", filter=Q(selected_choice__is_correct=True)),
        )
        .order_by("session_item__question__skill__code")
    )
    skill_scores = {
        row["session_item__question__skill__code"]: {
            "correct": row["correct"],
            "total": row["total"],
        }
        for row in rows
    }
    return {
        "lesson_code": session.lesson.code if session.lesson_id else None,
        "weak_skills": [
            skill_code
            for skill_code, score in skill_scores.items()
            if score["correct"] < 3
        ],
        "correct_count": sum(score["correct"] for score in skill_scores.values()),
        "total_count": sum(score["total"] for score in skill_scores.values()),
        "hint_used": Response.objects.filter(
            session_item__session=session,
            hint_used=True,
        ).exists(),
        "skill_scores": skill_scores,
    }


def build_query(evidence):
    weak_skills = ", ".join(evidence["weak_skills"]) or "none"
    lesson_code = evidence["lesson_code"] or "activity"
    return (
        f"Lesson: {lesson_code}\n"
        f"Weak skills: {weak_skills}\n"
        f"Correct: {evidence['correct_count']} of {evidence['total_count']}\n"
        f"Hint used: {'yes' if evidence['hint_used'] else 'no'}"
    )


def _session_action(session):
    try:
        return session.adaptive_decision.action
    except Decision.DoesNotExist:
        return Decision.Action.PROGRESS


def _contains_protected_answer_key(response_text):
    normalized = response_text.casefold()
    answer_keys = QuestionChoice.objects.filter(
        question__set_items__question_set__set_type=QuestionSet.SetType.PREPOST,
        is_correct=True,
    ).values_list("question__code", "label", "text")
    for question_code, label, answer_text in answer_keys:
        markers = (
            f"{question_code}:{label}",
            f"{question_code}: {label}",
            f"{question_code}={label}",
        )
        if any(marker.casefold() in normalized for marker in markers):
            return True
        compact_answer = answer_text.strip()
        if re.fullmatch(r"-?\d+(?:\.\d+)?", compact_answer):
            if re.search(
                rf"(?<![\w.]){re.escape(compact_answer)}(?![\w.])",
                response_text,
            ):
                return True
        elif compact_answer.casefold() in normalized:
            return True
    return False


def _contains_unverified_score(response_text, evidence):
    allowed_pair = (evidence["correct_count"], evidence["total_count"])
    for correct, total in re.findall(
        r"(?<![\w-])(\d+)\s*(?:/|out\s+of)\s*(\d+)(?!\w)",
        response_text,
        flags=re.IGNORECASE,
    ):
        if (int(correct), int(total)) != allowed_pair:
            return True
    if re.search(r"(?<![\w-])\d+(?:\.\d+)?\s*%", response_text):
        return True
    for score in re.findall(
        r"\b(?:score(?:d|\s+is|\s+of)?|got)\s*:?\s*(\d+)\b",
        response_text,
        flags=re.IGNORECASE,
    ):
        if int(score) != evidence["correct_count"]:
            return True
    return False


def _contradicts_action(response_text, action):
    normalized = response_text.casefold()
    has_progress = any(phrase in normalized for phrase in PROGRESS_PHRASES)
    has_additional = any(phrase in normalized for phrase in ADDITIONAL_PHRASES)
    has_foundational = any(phrase in normalized for phrase in FOUNDATIONAL_PHRASES)
    if action == Decision.Action.FOUNDATIONAL_EXERCISE:
        return has_progress or has_additional
    if action == Decision.Action.ADDITIONAL_EXERCISE:
        return has_progress or has_foundational
    if action == Decision.Action.PROGRESS:
        return has_additional or has_foundational
    return True


def validate_output(response, session, action):
    if not isinstance(response, str) or not response.strip():
        return False
    if len(response.split()) > MAX_OUTPUT_WORDS:
        return False
    normalized = response.casefold()
    if any(term in normalized for term in FORBIDDEN_TERMS):
        return False
    if "correct answer is" in normalized:
        return False
    if _contains_protected_answer_key(response):
        return False
    evidence = session_evidence(session)
    if _contains_unverified_score(response, evidence):
        return False
    if _contradicts_action(response, action):
        return False
    return True


def generate_fallback_draft(session):
    evidence = session_evidence(session)
    action = _session_action(session)
    return FeedbackDraft(
        feedback_text=deterministic_fallback(session, evidence, action),
        generation_status=SessionFeedback.GenerationStatus.FALLBACK,
        model_name=None,
    )


def generate_session_feedback(session):
    evidence = session_evidence(session)
    action = _session_action(session)
    fallback = FeedbackDraft(
        feedback_text=deterministic_fallback(session, evidence, action),
        generation_status=SessionFeedback.GenerationStatus.FALLBACK,
        model_name=None,
    )
    try:
        query_embedding, _ = get_embedding_client(purpose="query").embed(
            build_query(evidence)
        )
        chunks = retrieve(query_embedding, top_k=4, min_similarity=0.35)
        if not chunks:
            return fallback
        prompt = assemble_prompt(evidence, chunks, action)
        generator = GroqFeedbackClient()
        response = generator.generate(prompt)
        if not validate_output(response, session, action):
            return fallback
        return FeedbackDraft(
            feedback_text=response.strip(),
            generation_status=SessionFeedback.GenerationStatus.GENERATED,
            model_name=generator.model,
        )
    except Exception as exc:
        logger.warning(
            "Feedback generation failed for session %s; using fallback (%s).",
            session.pk,
            type(exc).__name__,
        )
        return fallback
