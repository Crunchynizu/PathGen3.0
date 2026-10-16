from dataclasses import dataclass
from math import isfinite


@dataclass(frozen=True)
class BKTParameters:
    p_l0: float = 0.30
    p_t: float = 0.09
    p_g: float = 0.10
    p_s: float = 0.09


@dataclass(frozen=True)
class BKTResult:
    p_before: float
    p_after_observation: float | None
    p_after_learning: float
    learning_transition_applied: bool


def _probability(value, name):
    value = float(value)
    if not isfinite(value) or value < 0.0 or value > 1.0:
        raise ValueError(f"{name} must be a finite probability in [0.0, 1.0].")
    return value


def _validate_result(value, *, inputs):
    if not isfinite(value) or value < 0.0 or value > 1.0:
        raise ValueError(f"BKT result is outside [0.0, 1.0]; inputs={inputs!r}")


def update_mastery(
    p,
    is_correct,
    p_t,
    p_g,
    p_s,
    *,
    apply_learning_transition=True,
    posterior_only=False,
):
    p = _probability(p, "p")
    p_t = _probability(p_t, "p_t")
    p_g = _probability(p_g, "p_g")
    p_s = _probability(p_s, "p_s")
    inputs = {
        "p": p,
        "is_correct": bool(is_correct),
        "p_t": p_t,
        "p_g": p_g,
        "p_s": p_s,
        "apply_learning_transition": bool(apply_learning_transition),
        "posterior_only": bool(posterior_only),
    }

    if is_correct:
        denominator = p * (1 - p_s) + (1 - p) * p_g
        if denominator == 0:
            raise ValueError(f"BKT observation denominator is zero; inputs={inputs!r}")
        p_posterior = (p * (1 - p_s)) / denominator
    else:
        denominator = p * p_s + (1 - p) * (1 - p_g)
        if denominator == 0:
            raise ValueError(f"BKT observation denominator is zero; inputs={inputs!r}")
        p_posterior = (p * p_s) / denominator

    learning_transition_applied = bool(
        apply_learning_transition and not posterior_only
    )
    if learning_transition_applied:
        p_new = p_posterior + (1 - p_posterior) * p_t
    else:
        p_new = p_posterior
    _validate_result(p_new, inputs=inputs)
    return BKTResult(
        p_before=p,
        p_after_observation=p_posterior,
        p_after_learning=p_new,
        learning_transition_applied=learning_transition_applied,
    )


def update_mastery_for_session(
    p,
    is_correct,
    p_t,
    p_g,
    p_s,
    *,
    session_type,
    hint_used=False,
):
    if session_type == "posttest":
        raise ValueError("Post-test responses must never be processed by BKT.")
    if session_type not in {
        "pretest",
        "regular",
        "additional",
        "foundational",
        "activity",
    }:
        raise ValueError(f"Unsupported BKT session type: {session_type!r}.")

    if session_type == "foundational" and hint_used:
        p = _probability(p, "p")
        p_t = _probability(p_t, "p_t")
        p_g = _probability(p_g, "p_g")
        p_s = _probability(p_s, "p_s")
        inputs = {
            "p": p,
            "is_correct": bool(is_correct),
            "p_t": p_t,
            "p_g": p_g,
            "p_s": p_s,
            "session_type": session_type,
            "hint_used": True,
        }
        p_new = p + (1 - p) * p_t
        _validate_result(p_new, inputs=inputs)
        return BKTResult(
            p_before=p,
            p_after_observation=None,
            p_after_learning=p_new,
            learning_transition_applied=True,
        )

    return update_mastery(
        p,
        is_correct,
        p_t,
        p_g,
        p_s,
        apply_learning_transition=session_type != "pretest",
        posterior_only=session_type == "pretest",
    )


def mastery_band(p_known):
    p_known = _probability(p_known, "p_known")
    if p_known < 0.50:
        return "np"
    if p_known < 0.80:
        return "dev"
    return "strong"
