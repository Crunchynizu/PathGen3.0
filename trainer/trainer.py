"""PathGen Q-learning trainer, built from new_q_learning_training.md (sections 2-8).

v4: every lesson is taught in one-skill parts (instructor decision 2026-10-16), so only v3's
one-skill "batch" family remains, renamed "part": each part ends in a 6-item exercise on ONE
skill, which passes with PART_PASS_CORRECT of 6. v3's two-skill "pair" family (Lessons 1 and
3, 2 skills x 3 items) is gone.

New in v4: each skill has its own BKT numbers, read from skill_params.json (the hand-over
format of the Junyi model). Each training episode simulates one skill's numbers. Since
2026-10-25 the file holds the Junyi fit (../model, variant "final", rounded to 6
decimals); the borrowed numbers it replaced are kept in skill_params_placeholder.json.

With one skill, weakest band == average band, so PathGen's key builder gives keys like
"(dev, dev, p)": six rows, np/dev/strong x p/f.
"""

import copy
import json
import os
import random
from dataclasses import dataclass

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL_PARAMS_PATH = os.path.join(HERE, "skill_params.json")


@dataclass(frozen=True)
class BKT:
    p_l0: float
    p_t: float
    p_g: float
    p_s: float


def load_skill_params(path=SKILL_PARAMS_PATH):
    """{skill code: BKT} from the hand-over file; extra fields (junyi_exercises, AUC...) are ignored."""
    with open(path) as f:
        skills = json.load(f)["skills"]
    params = {code: BKT(*(float(row[k]) for k in ("p_l0", "p_t", "p_g", "p_s"))) for code, row in skills.items()}
    for code, bkt in params.items():
        assert all(0.0 <= v <= 1.0 for v in vars(bkt).values()), f"{code}: BKT numbers must be probabilities"
        assert bkt.p_g + bkt.p_s < 1.0, f"{code}: guess + slip must stay below 1"
    return params


# --- Section 2: frozen runtime contract ---
SKILL_PARAMS = load_skill_params()
GAMMA = 0.60

BANDS = ("np", "dev", "strong")
ACTIONS = ("progress", "additional_exercise", "foundational_exercise")
REGULAR_ACTIONS = ACTIONS
ADDITIONAL_ACTIONS = ("progress", "foundational_exercise")
CONTEXTS = ("regular", "additional")
EXERCISE_ITEMS = 6           # every regular/additional exercise has six items; burden is per exercise

PART_PASS_CORRECT = 4        # agreed by the group 2026-10-03 (two-thirds); 3 of 6 kept as a sensitivity
PART_FOUNDATIONAL_ITEMS = 3  # agreed 2026-10-03; 6 kept as a sensitivity
# Agreed by the group 2026-10-03: a student who passes a part (4 of 6) moves on to the next
# part. Training alone sends even passing students to an additional exercise, because the
# simulator treats extra questions as nearly free; under BKT a 4-of-6 pass already means
# strong mastery (about 0.98 from P(L0) = 0.30).


@dataclass(frozen=True)
class Family:
    name: str
    n_skills: int
    pass_results: tuple
    band_pairs: tuple         # reachable (weakest, average) pairs
    additional_items: int     # per skill
    pass_correct: int         # correct answers per skill needed to pass
    foundational_items: int   # per failed skill
    pass_moves_on: bool       # declared rule: passing the exercise always means progress
    near_miss: bool = False   # sensitivity: split a fail into near miss "n" (one short) and far miss "f"

    def keys(self):
        return [state_key(w, a, p) for w, a in self.band_pairs for p in self.pass_results]

    def owns(self, key):
        return key in self.keys()


# --- Section 3: reachable states ---
PART = Family("part", 1, ("p", "f"), (("np", "np"), ("dev", "dev"), ("strong", "strong")),
              6, PART_PASS_CORRECT, PART_FOUNDATIONAL_ITEMS, True)
FAMILIES = (PART,)


def state_key(weakest, average, pass_result):
    return f"({weakest}, {average}, {pass_result})"


def pass_of(key):
    return key.strip("()").split(", ")[2]


def all_passed(key):
    return set(pass_of(key)) == {"p"}


def reachable_training_keys(family=None):
    return [k for f in ((family,) if family else FAMILIES) for k in f.keys()]


def all_artifact_keys():
    return PART.keys()


def allowed_actions(context):
    return REGULAR_ACTIONS if context == "regular" else ADDITIONAL_ACTIONS


def runtime_choice(row, mask):
    """PathGen: tied names sorted alphabetically, then argmax."""
    return sorted(mask, key=lambda a: (-row[a], a))[0]


def td_target(reward, terminated, max_next, gamma=GAMMA):
    return reward if terminated else reward + gamma * max_next


# --- Section 5: student and BKT simulation ---
def band(p):
    if p < 0.50:
        return "np"
    if p < 0.80:
        return "dev"
    return "strong"


def state_of(mastery, pass_result):
    return state_key(band(min(mastery)), band(sum(mastery) / len(mastery)), pass_result)


def clamp(p):
    return min(1.0, max(0.0, p))   # floating-point tolerance only


def answer_item(p, rng, bkt):
    correct = rng.random() < p * (1 - bkt.p_s) + (1 - p) * bkt.p_g
    if correct:
        post = p * (1 - bkt.p_s) / (p * (1 - bkt.p_s) + (1 - p) * bkt.p_g)
    else:
        post = p * bkt.p_s / (p * bkt.p_s + (1 - p) * (1 - bkt.p_g))
    return clamp(post + (1 - post) * bkt.p_t), correct


def hinted_item(p, bkt):
    """Hinted foundational response: skip the posterior, apply P(T) only."""
    return clamp(p + (1 - p) * bkt.p_t)


def failed_skills(pass_result):
    return [i for i, c in enumerate(pass_result) if c != "p"]


def pass_letter(correct, family):
    if correct >= family.pass_correct:
        return "p"
    if family.near_miss and correct == family.pass_correct - 1:
        return "n"
    return "f"


def questions_assigned(action, pass_result, family=PART):
    if action == "progress":
        return 0
    if action == "additional_exercise":
        return family.n_skills * family.additional_items
    return family.foundational_items * len(failed_skills(pass_result))


def step(mastery, pass_result, context, action, params, rng, family=PART, bkt=None):
    """One transition. Returns (mastery, pass_result, next_context, reward, terminated)."""
    assert action in allowed_actions(context)
    bkt = bkt or next(iter(SKILL_PARAMS.values()))
    m = list(mastery)
    if action == "additional_exercise":
        passes = []
        for i in range(len(m)):
            correct = 0
            for _ in range(family.additional_items):
                m[i], c = answer_item(m[i], rng, bkt)
                correct += c
            passes.append(pass_letter(correct, family))
        next_pass, terminated = "".join(passes), False
    elif action == "foundational_exercise":
        for i in failed_skills(pass_result):
            for _ in range(family.foundational_items):
                if rng.random() < params["hint_probability"]:
                    m[i] = hinted_item(m[i], bkt)
                else:
                    m[i], _ = answer_item(m[i], rng, bkt)
        next_pass, terminated = pass_result, True
    else:
        next_pass, terminated = pass_result, True

    # Section 7 reward
    gain = sum(m) / len(m) - sum(mastery) / len(mastery)
    burden = questions_assigned(action, pass_result, family) / EXERCISE_ITEMS
    reward = gain - params["burden_weight"] * burden + params["completion_utility"] * terminated
    return m, next_pass, (None if terminated else "additional"), reward, terminated


# --- Section 6: balanced exploring starts ---
def start_pairs(family):
    return [(ctx, w, a, p) for ctx in CONTEXTS for w, a in family.band_pairs for p in family.pass_results]


def sample_mastery(weakest, average, rng, n_skills=1):
    while True:
        m = [rng.random() for _ in range(n_skills)]
        if band(min(m)) == weakest and band(sum(m) / n_skills) == average:
            return m


def distinct_params(skill_params):
    """Skills with the same numbers simulate the same student, so episodes draw over the distinct
    parameter sets. With one set (the placeholders) no draw is made and runs match v3 exactly."""
    return sorted(set(skill_params.values()), key=lambda b: (b.p_l0, b.p_t, b.p_g, b.p_s))


# --- Section 8: Q-learning ---
# Review fix: the guide's 1/n^0.60 leaves too much seed-to-seed noise for gate 4 even at
# 300k episodes. With gamma = 0.6 and at most two decisions, a plain sample average (1/n)
# has no slow-convergence downside, and it passed gate 4 at 75k episodes.
ALPHA_EXPONENT = 1.0


def train_seed(seed, params, episodes, gamma=GAMMA, alpha_exponent=ALPHA_EXPONENT, family=PART,
               skill_params=None):
    """Returns raw Q, visit counts per (context, state, action), and the 80% checkpoint."""
    rng = random.Random(seed)
    param_sets = distinct_params(skill_params or SKILL_PARAMS)
    keys = family.keys()
    starts = start_pairs(family)
    Q = {k: {a: 0.0 for a in ACTIONS} for k in keys}
    # visits per (context, state, action) for coverage; updates per shared cell for alpha,
    # since progress/foundational cells receive updates from both contexts
    visits = {f"{ctx}|{k}|{a}": 0 for ctx in CONTEXTS for k in keys for a in allowed_actions(ctx)}
    updates = {k: {a: 0 for a in ACTIONS} for k in keys}
    checkpoint = None

    for episode in range(episodes):
        if episode == int(episodes * 0.8):
            checkpoint = copy.deepcopy(Q)
        context, weakest, average, pass_result = starts[episode % len(starts)]
        bkt = param_sets[0] if len(param_sets) == 1 else rng.choice(param_sets)
        mastery = sample_mastery(weakest, average, rng, family.n_skills)
        while True:
            state = state_of(mastery, pass_result)
            action = rng.choice(allowed_actions(context))
            mastery, pass_result, next_context, reward, terminated = step(
                mastery, pass_result, context, action, params, rng, family, bkt)
            vkey = f"{context}|{state}|{action}"
            visits[vkey] += 1
            updates[state][action] += 1
            alpha = 1.0 / (updates[state][action] ** alpha_exponent)
            max_next = 0.0
            if not terminated:
                next_state = state_of(mastery, pass_result)
                max_next = max(Q[next_state][a] for a in allowed_actions(next_context))
            Q[state][action] += alpha * (td_target(reward, terminated, max_next, gamma) - Q[state][action])
            if terminated:
                break
            context = next_context

    return {"Q": Q, "visits": visits, "checkpoint_80": checkpoint}
