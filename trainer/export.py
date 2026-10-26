"""Seed consolidation, declared policy and export (new_q_learning_training.md sections 9-10,
with the fixes agreed after review).

Instead of nudging raw Q-values by 1e-6 (which scaling + rounding erases), each row gets a
declared ranking of its three actions:
  1. median raw Q order;
  2. section 9 practical-tie rule moves its choice to the top of unstable rows;
  3. all-passed rule (p rows): progress ranks above foundational
     (foundational assigns 0 questions there);
  4. moves-on rule: a passed part always means progress.
The export then enforces that ranking with a gap that survives rounding.
"""

import math
import statistics

from trainer import (ACTIONS, ADDITIONAL_ACTIONS, PART, REGULAR_ACTIONS, all_artifact_keys,
                     all_passed, pass_of, questions_assigned, runtime_choice)

TIE_MARGIN = 0.01
EXPORT_GAP = 0.001          # minimum gap between ranked actions, after rounding
DECIMALS = 6


def choice(ranking, mask):
    """The action PathGen picks under `mask` if the row follows `ranking`."""
    return next(a for a in ranking if a in mask)


def consolidate(tables, family=PART):
    """Median raw Q per cell over seeds, plus per-state stability info (section 9)."""
    median, info = {}, {}
    for k in family.keys():
        median[k] = {a: statistics.median(t[k][a] for t in tables) for a in ACTIONS}
        picks = [choice(declared_ranking(t[k], k, family=family), REGULAR_ACTIONS) for t in tables]
        counts = {a: picks.count(a) for a in ACTIONS}
        ranked = sorted(ACTIONS, key=lambda a: (-median[k][a], a))
        margin = median[k][ranked[0]] - median[k][ranked[1]]
        info[k] = {
            "min": {a: min(t[k][a] for t in tables) for a in ACTIONS},
            "max": {a: max(t[k][a] for t in tables) for a in ACTIONS},
            "chosen_action_count": counts,
            "top_two_margin": margin,
            "seed_stable": max(counts.values()) >= len(tables) - 1,
            "unstable": margin < TIE_MARGIN or max(counts.values()) < len(tables) - 1,
        }
    return median, info


def practical_tie_choice(row, key, family=PART):
    """1. progress if within 0.01 of the top; 2. fewer questions; 3. additional over foundational."""
    top = max(row.values())
    if row["progress"] >= top - TIE_MARGIN:
        return "progress"
    near_top = [a for a in ACTIONS if row[a] >= top - TIE_MARGIN]
    return min(near_top, key=lambda a: (questions_assigned(a, pass_of(key), family),
                                        a != "additional_exercise"))


def declared_ranking(row, key, unstable=False, family=PART, rules=("pass", "moves on")):
    """Best-first ranking of the three actions for one row. `rules` lets declare() see what
    each declared rule changed."""
    ranking = sorted(ACTIONS, key=lambda a: (-row[a], a))
    if unstable:
        top = practical_tie_choice(row, key, family)
        ranking = [top] + [a for a in ranking if a != top]
    if "pass" in rules and all_passed(key) and             ranking.index("foundational_exercise") < ranking.index("progress"):
        ranking.remove("progress")
        ranking.insert(ranking.index("foundational_exercise"), "progress")
    if "moves on" in rules and family.pass_moves_on and all_passed(key):
        ranking = ["progress"] + [a for a in ranking if a != "progress"]
    return ranking


def declare(median, info, family=PART):
    """Declared ranking per row, and what set its choices: "learned" or "tie rule", plus
    "pass rule" / "moves-on rule" when that rule changed the choice under either mask."""
    rankings, source = {}, {}
    for k, row in median.items():
        unstable = info[k]["unstable"]
        steps = [declared_ranking(row, k, unstable, family, rules)
                 for rules in ((), ("pass",), ("pass", "moves on"))]
        rankings[k] = steps[-1]
        parts = ["tie rule" if unstable else "learned"]
        for label, before, after in (("pass rule", steps[0], steps[1]),
                                     ("moves-on rule", steps[1], steps[2])):
            if any(choice(before, m) != choice(after, m) for m in (REGULAR_ACTIONS, ADDITIONAL_ACTIONS)):
                parts.append(label)
        source[k] = " + ".join(parts)
    return rankings, source


def export_rows(median, rankings, gap=EXPORT_GAP):
    """Per-row affine map to [0.05, 0.95], then lower any value that is not at least `gap`
    below the action ranked above it. Rounded values are rechecked by policy_check.
    `median` and `rankings` cover every trained row."""
    q_values = {}
    for k in all_artifact_keys():
        row, ranking = median[k], rankings[k]
        low, high = min(row.values()), max(row.values())
        span = high - low
        out = {a: (0.05 + 0.90 * (row[a] - low) / span) if span > 0 else 0.05 for a in ACTIONS}
        out[ranking[0]] = max(out[ranking[0]], 0.05 + 2 * gap)
        for upper, lower in zip(ranking, ranking[1:]):
            out[lower] = min(out[lower], out[upper] - gap)
        q_values[k] = {a: round(float(out[a]), DECIMALS) for a in ACTIONS}
    return q_values


def policy_check(rankings, q_values):
    """Rows where the exported values do not reproduce the declared choice under a mask."""
    return [(k, mask) for k, ranking in rankings.items()
            for mask in (REGULAR_ACTIONS, ADDITIONAL_ACTIONS)
            if runtime_choice(q_values[k], mask) != choice(ranking, mask)]


def contract_problems(artifact):
    q = artifact["q_values"]
    problems = []
    if artifact["_meta"].get("policy_version") != "Q-LEARNING-V1":
        problems.append("policy_version")
    if sorted(q) != sorted(all_artifact_keys()):
        problems.append(f"{len(q)} rows / wrong keys")
    for k, row in q.items():
        if set(row) != set(ACTIONS):
            problems.append(f"{k}: actions")
        for a, v in row.items():
            if not isinstance(v, float) or not math.isfinite(v) or not 0.0 <= v <= 1.0:
                problems.append(f"{k}.{a} = {v!r}")
        if all_passed(k):
            if runtime_choice(row, ADDITIONAL_ACTIONS) != "progress":
                problems.append(f"{k}: after-additional mask selects "
                                f"{runtime_choice(row, ADDITIONAL_ACTIONS)} (must be progress)")
            if runtime_choice(row, REGULAR_ACTIONS) == "foundational_exercise":
                problems.append(f"{k}: regular mask selects foundational_exercise")
    return problems
