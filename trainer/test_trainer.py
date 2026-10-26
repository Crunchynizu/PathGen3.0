"""Section 11 tests, tests for the review fixes, the one-skill part rows and per-skill BKT numbers.
Run: python test_trainer.py (after run_all.py for the artifact tests)."""

import json
import os
import random
import tempfile
from dataclasses import replace

from export import choice, declared_ranking, contract_problems, export_rows, policy_check
from trainer import (ACTIONS, ADDITIONAL_ACTIONS, BKT, PART, REGULAR_ACTIONS, SKILL_PARAMS,
                     all_artifact_keys, allowed_actions, answer_item, distinct_params,
                     load_skill_params, questions_assigned, reachable_training_keys, step,
                     td_target, train_seed)

HERE = os.path.dirname(os.path.abspath(__file__))
PARAMS = {"burden_weight": 0.02, "completion_utility": 0.02, "hint_probability": 0.5}
NEAR = replace(PART, name="part-near-miss", pass_results=("p", "n", "f"), near_miss=True)


class Fixed:
    """An rng whose random() always returns `value`."""

    def __init__(self, value):
        self.value = value

    def random(self):
        return self.value


def test_terminal_target_does_not_bootstrap():
    assert td_target(reward=0.2, terminated=True, max_next=99.0) == 0.2


def test_additional_transition_masks_additional_action():
    assert allowed_actions("additional") == ("progress", "foundational_exercise")


def test_artifact_has_the_six_part_rows():
    assert PART.keys() == ["(np, np, p)", "(np, np, f)", "(dev, dev, p)", "(dev, dev, f)",
                           "(strong, strong, p)", "(strong, strong, f)"]
    assert all_artifact_keys() == PART.keys() == reachable_training_keys()


def test_export_preserves_argmax_for_every_allowed_mask():
    # includes exact ties and tiny gaps, which the original 1e-6 nudge could not survive
    rng = random.Random(0)
    for _ in range(300):
        median, rankings = {}, {}
        for k in PART.keys():
            base = rng.uniform(-0.2, 0.4)
            row = {a: rng.choice([base, base + 1e-9, base + rng.uniform(-0.3, 0.3)]) for a in ACTIONS}
            median[k] = row
            rankings[k] = declared_ranking(row, k, unstable=rng.random() < 0.5, family=PART)
        assert not policy_check(rankings, export_rows(median, rankings))


def test_exported_values_in_range():
    median = {k: {a: 0.0 for a in ACTIONS} for k in reachable_training_keys()}   # all flat
    rankings = {k: declared_ranking(median[k], k, family=PART) for k in median}
    for row in export_rows(median, rankings).values():
        assert all(0.0 <= v <= 1.0 for v in row.values())


def test_part_question_counts():
    assert questions_assigned("additional_exercise", "f", PART) == 6
    assert questions_assigned("foundational_exercise", "f", PART) == PART.foundational_items
    assert questions_assigned("foundational_exercise", "p", PART) == 0


def test_additional_uses_six_items_and_the_part_pass_rule():
    # a student who always answers correctly passes; one who never does fails
    m, result, ctx, _, terminated = step([0.5], "f", "regular", "additional_exercise", PARAMS, Fixed(0.0), PART)
    assert (result, ctx, terminated) == ("p", "additional", False)
    _, result, _, _, _ = step([0.5], "f", "regular", "additional_exercise", PARAMS, Fixed(0.999), PART)
    assert result == "f"


def test_passed_rows_rank_progress_above_foundational():
    tied = {"progress": 0.02, "additional_exercise": 0.18, "foundational_exercise": 0.02}
    ranking = declared_ranking(tied, "(dev, dev, p)", family=PART)
    assert choice(ranking, ADDITIONAL_ACTIONS) == "progress"


def test_passed_part_moves_on():
    # training prefers additional here; the declared rule overrides it for passed rows only
    learned = {"progress": 0.02, "additional_exercise": 0.04, "foundational_exercise": 0.02}
    for key in ("(np, np, p)", "(dev, dev, p)", "(strong, strong, p)"):
        assert choice(declared_ranking(learned, key, family=PART), REGULAR_ACTIONS) == "progress"
    assert choice(declared_ranking(learned, "(strong, strong, f)", family=PART),
                  REGULAR_ACTIONS) == "additional_exercise"


def test_training_covers_every_cell():
    run = train_seed(1, PARAMS, 6000, family=PART)
    assert set(run["Q"]) == set(PART.keys())
    assert min(run["visits"].values()) > 0


# --- per-skill BKT numbers ---
def test_skill_params_file_loads():
    assert set(SKILL_PARAMS) == {f"S{i}" for i in range(1, 8)}
    assert all(isinstance(b, BKT) for b in SKILL_PARAMS.values())


def test_hand_over_file_with_extra_fields_loads():
    hand_over = {"dataset": "Junyi 2015", "method": "pyBKT EM", "skills": {
        "S2": {"p_l0": 0.35, "p_t": 0.12, "p_g": 0.25, "p_s": 0.08, "junyi_exercises": ["x"],
               "n_students": 10, "n_answers": 100, "test_auc": 0.7, "test_auc_borrowed": 0.6}}}
    with tempfile.TemporaryDirectory() as d:
        path = os.path.join(d, "skill_params.json")
        with open(path, "w") as f:
            json.dump(hand_over, f)
        assert load_skill_params(path) == {"S2": BKT(0.35, 0.12, 0.25, 0.08)}


def test_skills_with_equal_numbers_count_once():
    same = BKT(0.3, 0.09, 0.1, 0.09)
    assert distinct_params({"S1": same, "S2": same}) == [same]
    assert len(distinct_params({"S1": same, "S2": BKT(0.3, 0.2, 0.1, 0.09)})) == 2


def test_skill_numbers_change_the_simulated_student():
    slow, fast = BKT(0.3, 0.05, 0.1, 0.09), BKT(0.3, 0.30, 0.1, 0.09)
    p_slow, _ = answer_item(0.4, Fixed(0.0), slow)
    p_fast, _ = answer_item(0.4, Fixed(0.0), fast)
    assert p_fast > p_slow


def test_training_with_two_parameter_sets_covers_every_cell():
    skills = {"S1": BKT(0.3, 0.05, 0.1, 0.09), "S2": BKT(0.3, 0.30, 0.25, 0.05)}
    run = train_seed(1, PARAMS, 6000, family=PART, skill_params=skills)
    assert min(run["visits"].values()) > 0


# --- near-miss sensitivity ---
def test_near_miss_letter():
    # 3 of 6 correct: one short of passing is "n" in the near-miss family, "f" otherwise
    class Pattern:
        def __init__(self, answers):
            self.answers = iter(answers)

        def random(self):
            return next(self.answers)
    three = [0.0, 0.0, 0.0, 0.999, 0.999, 0.999]
    _, result, _, _, _ = step([0.5], "f", "regular", "additional_exercise", PARAMS, Pattern(three), NEAR)
    assert result == "n"
    _, result, _, _, _ = step([0.5], "f", "regular", "additional_exercise", PARAMS, Pattern(three), PART)
    assert result == "f"
    assert questions_assigned("foundational_exercise", "n", NEAR) == NEAR.foundational_items


def test_near_miss_training_covers_every_cell():
    run = train_seed(1, PARAMS, 9000, family=NEAR)
    assert set(run["Q"]) == set(NEAR.keys()) and len(NEAR.keys()) == 9
    assert min(run["visits"].values()) > 0


# --- artifact ---
def test_artifact_contract():
    with open(os.path.join(HERE, "output", "q_table.json")) as f:
        artifact = json.load(f)
    problems = contract_problems(artifact)
    assert not problems, "\n    ".join(problems)


def test_artifact_matches_pathgen_loader_contract():
    # the checks apps/adaptive/q_learning.py makes once it requires the part rows
    with open(os.path.join(HERE, "output", "q_table.json")) as f:
        data = json.load(f)
    assert data["_meta"]["policy_version"] == "Q-LEARNING-V1"
    assert sorted(data["q_values"]) == sorted(PART.keys())
    for row in data["q_values"].values():
        assert set(row) == set(ACTIONS)
        assert all(isinstance(v, float) and 0.0 <= v <= 1.0 for v in row.values())


if __name__ == "__main__":
    failed = 0
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            try:
                fn()
                print(f"PASS  {name}")
            except (AssertionError, OSError) as e:
                failed += 1
                print(f"FAIL  {name}\n    {e}")
    print(f"\n{failed} failed")
