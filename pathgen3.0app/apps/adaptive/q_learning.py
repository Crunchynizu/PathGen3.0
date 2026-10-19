import json
import logging
from functools import lru_cache
from math import isfinite
from pathlib import Path


logger = logging.getLogger(__name__)

POLICY_VERSION = "Q-LEARNING-V1"
ACTIONS = {
    "progress",
    "additional_exercise",
    "foundational_exercise",
}
Q_TABLE_PATH = Path(__file__).with_name("q_table.json")
BANDS = ("np", "dev", "strong")


def state_key(weakest_band, average_band, pass_result):
    return f"({weakest_band}, {average_band}, {pass_result})"


# One skill per lesson part, so weakest = average: np/dev/strong x passed/failed.
PART_STATE_KEYS = frozenset(state_key(band, band, result) for band in BANDS for result in ("p", "f"))


def _validate_q_values(data):
    if not isinstance(data, dict):
        raise ValueError("The Q-table root must be an object.")
    meta = data.get("_meta")
    if not isinstance(meta, dict) or meta.get("policy_version") != POLICY_VERSION:
        raise ValueError("The Q-table policy version is invalid.")
    q_values = data.get("q_values")
    if not isinstance(q_values, dict) or not PART_STATE_KEYS <= set(q_values):
        raise ValueError("The Q-table must contain the six one-skill part rows.")
    for row in q_values.values():
        if not isinstance(row, dict) or set(row) != ACTIONS:
            raise ValueError("Every Q-table row must contain exactly three actions.")
        if any(
            not isinstance(value, float)
            or not isfinite(value)
            or value < 0.0
            or value > 1.0
            for value in row.values()
        ):
            raise ValueError("Every Q-value must be a float in [0.0, 1.0].")
    return q_values


@lru_cache(maxsize=1)
def load_q_table():
    try:
        data = json.loads(Q_TABLE_PATH.read_text(encoding="utf-8"))
        return _validate_q_values(data)
    except Exception as exc:  # The runtime policy must never interrupt learning.
        logger.warning("Q-table unavailable or invalid; using progress fallback: %s", exc)
        return {}


def decide(weakest_band, average_band, pass_result, allowed_actions):
    try:
        row = load_q_table().get(
            state_key(weakest_band, average_band, pass_result)
        )
        if not isinstance(row, dict) or set(row) != ACTIONS:
            raise ValueError("The requested Q-table row is missing or malformed.")

        available = set(allowed_actions)
        candidates = {
            action: value
            for action, value in row.items()
            if action in available
            and isinstance(value, float)
            and isfinite(value)
            and 0.0 <= value <= 1.0
        }
        if not candidates:
            raise ValueError("All Q-Learning actions are masked.")

        chosen_action = max(sorted(candidates), key=candidates.__getitem__)
        return chosen_action, "q_learning_argmax"
    except Exception as exc:  # Fallback is part of the public runtime contract.
        logger.warning("Q-Learning decision failed; using progress fallback: %s", exc)
        return "progress", "q_learning_missing_fallback"
