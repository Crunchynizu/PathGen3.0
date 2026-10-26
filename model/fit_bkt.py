"""Fit standard BKT per skill on train.csv, score test.csv once, compare fit variants.

    python fit_bkt.py <dir with train.csv and test.csv>

Fitting is maximum likelihood (the exact BKT forward algorithm) with scipy's L-BFGS-B,
which takes parameter limits directly, so no patched pyBKT is needed. Each fit starts
from several points and keeps the best. Variants, all decided before looking at test
results:

    unconstrained  every parameter free in (0, 1); comparable to a plain pyBKT EM fit
    bounded        option A: P(G) <= 0.3 and P(S) <= 0.1, the usual limits in the BKT
                   literature (Baker, Corbett & Aleven 2008; Beck & Chang 2007)
    fixed_guess    option B: P(G) = 0.25, the blind-guess rate on PathGen's 4-choice
                   questions; the other three free
    final          the version PathGen uses (group decision 2026-10-25): option A plus
                   P(T) <= 0.3, because ordering negatives (S5, 92% correct on Junyi)
                   otherwise fits P(T) = 0.74 and any score ends "strong". P(L0) stays
                   Junyi's own estimate; PathGen's pre-test updates it before lessons.

The borrowed numbers PathGen used before (0.30 / 0.09 / 0.10 / 0.09) are scored too.
Outputs go to ./output: one skill_params_<variant>.json per variant in the format the
v4 trainer reads, and metrics.csv.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sys
from concurrent.futures import ProcessPoolExecutor
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from scipy.optimize import minimize
from sklearn.metrics import roc_auc_score

HERE = Path(__file__).resolve().parent
OUT = HERE / "output"
MAP = HERE / "skill_map.csv"
SKILLS = [f"S{i}" for i in range(1, 8)]
KEYS = ("p_l0", "p_t", "p_g", "p_s")
EPS = 1e-4
BORROWED = {"p_l0": 0.30, "p_t": 0.09, "p_g": 0.10, "p_s": 0.09}
VARIANTS = {
    # name: bounds for (p_l0, p_t, p_g, p_s)
    "unconstrained": [(EPS, 1 - EPS)] * 4,
    "bounded": [(EPS, 1 - EPS), (EPS, 1 - EPS), (EPS, 0.30), (EPS, 0.10)],
    "fixed_guess": [(EPS, 1 - EPS), (EPS, 1 - EPS), (0.25, 0.25), (EPS, 1 - EPS)],
    "final": [(EPS, 1 - EPS), (EPS, 0.30), (EPS, 0.30), (EPS, 0.10)],
}
STARTS = [  # (p_l0, p_t, p_g, p_s); clipped into each variant's bounds
    (0.30, 0.09, 0.10, 0.09),
    (0.50, 0.05, 0.25, 0.05),
    (0.20, 0.20, 0.20, 0.10),
    (0.70, 0.02, 0.15, 0.15),
    (0.40, 0.40, 0.05, 0.02),
    (0.10, 0.10, 0.30, 0.20),
]
# PathGen's view of the result: mastery band after one 6-question lesson part.
PATTERNS = {
    "6/6": [1, 1, 1, 1, 1, 1],
    "5/6 missed last": [1, 1, 1, 1, 1, 0],
    "5/6 missed first": [0, 1, 1, 1, 1, 1],
    "4/6 missed last two": [1, 1, 1, 1, 0, 0],
    "4/6 missed first two": [0, 0, 1, 1, 1, 1],
    "3/6 missed last three": [1, 1, 1, 0, 0, 0],
    "2/6": [1, 0, 0, 1, 0, 0],
}


@dataclass
class Sequences:
    """Each student's answers on one skill, students sorted longest first."""
    y: np.ndarray        # all answers, student after student
    starts: np.ndarray   # index of each student's first answer in y
    active: np.ndarray   # active[t] = number of students with more than t answers


def read_split(path: Path) -> dict[str, Sequences]:
    by_skill: dict[str, dict[str, list[int]]] = {s: {} for s in SKILLS}
    with path.open(encoding="utf-8", newline="") as f:
        reader = csv.reader(f)
        assert next(reader) == ["user_id", "skill_code", "time_done", "y"]
        for user, skill, _, y in reader:  # already ordered by student and time
            by_skill[skill].setdefault(user, []).append(int(y))
    out = {}
    for skill, users in by_skill.items():
        seqs = sorted(users.values(), key=len, reverse=True)
        lengths = np.array([len(s) for s in seqs])
        starts = np.concatenate([[0], np.cumsum(lengths)[:-1]])
        active = np.array([(lengths > t).sum() for t in range(lengths.max())])
        out[skill] = Sequences(np.concatenate(seqs).astype(np.int8), starts, active)
    return out


def forward(seq: Sequences, p_l0, p_t, p_g, p_s):
    """One-step-ahead P(correct) for every answer; mastery updates after each answer.

    Tracks q = P(not mastered) rather than P(mastered). After a long run of correct
    answers mastery is within 1e-16 of 1; stored as p it rounds to exactly 1.0, after
    which wrong answers can no longer lower it, and whether that rounding happens
    flips with tiny parameter changes (a jump in the likelihood the optimiser cannot
    handle). Stored as q, the small number keeps its precision. Same BKT formulas.
    """
    pred = np.empty(len(seq.y))
    q = np.full(len(seq.starts), 1 - p_l0)
    for t, n in enumerate(seq.active):
        idx = seq.starts[:n] + t
        y = seq.y[idx]
        qn = q[:n]
        m_right = (1 - qn) * (1 - p_s)   # mastered and no slip
        n_right = qn * p_g               # not mastered but guessed
        correct = m_right + n_right
        pred[idx] = correct
        wrong_n = qn * (1 - p_g)
        q_post = np.where(y == 1, n_right / correct, wrong_n / ((1 - qn) * p_s + wrong_n))
        q[:n] = np.maximum(q_post * (1 - p_t), 1e-300)
    return pred


def neg_log_likelihood(params, seq: Sequences) -> float:
    pred = np.clip(forward(seq, *params), 1e-12, 1 - 1e-12)
    return -float(np.sum(np.where(seq.y == 1, np.log(pred), np.log(1 - pred))))


def fit(job):
    skill, variant, seq = job
    bounds = VARIANTS[variant]
    results = []
    for start in STARTS:
        x0 = [min(max(v, lo), hi) for v, (lo, hi) in zip(start, bounds)]
        results.append(minimize(neg_log_likelihood, x0, args=(seq,), method="L-BFGS-B", bounds=bounds))
    best = min(results, key=lambda r: r.fun)
    params = dict(zip(KEYS, (float(v) for v in best.x)))
    at_limit = [k for k, v, (lo, hi) in zip(KEYS, best.x, bounds) if lo < hi and (abs(v - hi) < 1e-3 or abs(v - lo) < 1e-3)]
    # How many starts ended at the same answer (log-likelihood within 0.5, parameters within 0.01)
    agree = sum(r.fun - best.fun < 0.5 and max(abs(r.x - best.x)) < 0.01 for r in results)
    return skill, variant, params, float(best.fun), at_limit + [f"starts_agree={agree}/{len(STARTS)}"]


def scores(seq: Sequences, params: dict) -> dict:
    pred = forward(seq, *(params[k] for k in KEYS))
    y = seq.y.astype(int)
    clipped = np.clip(pred, 1e-12, 1 - 1e-12)
    rate = y.mean()
    return {
        "auc": float(roc_auc_score(y, pred)),
        "brier": float(np.mean((pred - y) ** 2)),
        "log_loss": float(-np.mean(np.where(y == 1, np.log(clipped), np.log(1 - clipped)))),
        "accuracy": float(np.mean((pred >= 0.5) == y)),
        "baseline_accuracy": float(max(rate, 1 - rate)),
    }


def band(p: float) -> str:
    return "np" if p < 0.5 else "dev" if p < 0.8 else "strong"


def mastery_after(params: dict, answers: list[int]) -> float:
    p = params["p_l0"]
    for a in answers:
        c = p * (1 - params["p_s"]) + (1 - p) * params["p_g"]
        post = p * (1 - params["p_s"]) / c if a else p * params["p_s"] / (1 - c)
        p = post + (1 - post) * params["p_t"]
    return p


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main(data_dir: Path) -> None:
    OUT.mkdir(exist_ok=True)
    train = read_split(data_dir / "train.csv")
    jobs = [(s, v, train[s]) for v in VARIANTS for s in SKILLS]
    with ProcessPoolExecutor(max_workers=6) as pool:
        fitted = {(s, v): (p, nll, lim) for s, v, p, nll, lim in pool.map(fit, jobs)}
    print("Fitting done; scoring the test set once.", flush=True)

    test = read_split(data_dir / "test.csv")
    mapping = {s: [] for s in SKILLS}
    with MAP.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            mapping[row["skill_code"]].append({"exercise": row["exercise"], "problem_type": row["problem_type"]})
    build = json.loads((data_dir / "build_summary.json").read_text(encoding="utf-8"))
    hashes = {"train_sha256": sha256(data_dir / "train.csv"), "test_sha256": sha256(data_dir / "test.csv"),
              "skill_map_sha256": sha256(MAP)}

    rows = []
    for s in SKILLS:
        n_train, n_test = len(train[s].y), len(test[s].y)
        for v in ["borrowed", *VARIANTS]:
            params, nll, lim = (BORROWED, None, []) if v == "borrowed" else fitted[(s, v)]
            rows.append({"skill": s, "variant": v, **{k: round(params[k], 4) for k in KEYS},
                         "at_limit": " ".join(lim), "train_answers": n_train, "test_answers": n_test,
                         "train_students": len(train[s].starts), "test_students": len(test[s].starts),
                         **{k: round(x, 4) for k, x in scores(test[s], params).items()},
                         **{f"band {name}": f"{mastery_after(params, a):.2f} {band(mastery_after(params, a))}"
                            for name, a in PATTERNS.items()},
                         "start": f"{params['p_l0']:.2f} {band(params['p_l0'])}"})

    for v in VARIANTS:
        payload = {
            "dataset": "Junyi Academy Math Practicing Log, January 2015 release (all mapped answers)",
            "method": f"standard BKT, maximum likelihood (L-BFGS-B, {len(STARTS)} starts), variant '{v}'",
            "bounds": dict(zip(KEYS, VARIANTS[v])),
            "label_rule": "y=1 iff first attempt correct without a hint (Junyi correct field)",
            "split": "student-disjoint, 20% of students held out, seed 42, no row cap",
            **hashes,
            "skills": {r["skill"]: {**{k: fitted[(r["skill"], v)][0][k] for k in KEYS},
                                    "junyi_exercises": mapping[r["skill"]],
                                    "n_train_answers": r["train_answers"], "n_train_students": r["train_students"],
                                    "test_auc": r["auc"], "test_brier": r["brier"]}
                       for r in rows if r["variant"] == v},
        }
        (OUT / f"skill_params_{v}.json").write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")

    with (OUT / "metrics.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    (OUT / "build_summary.json").write_text(json.dumps({**build, **hashes}, indent=2) + "\n", encoding="utf-8")
    for r in rows:
        print(r["skill"], f"{r['variant']:<13}", *(f"{r[k]:.3f}" for k in KEYS), f"[{r['at_limit']}]",
              f"AUC {r['auc']:.3f} Brier {r['brier']:.3f}", "|", r["band 5/6 missed last"], "|", r["band 4/6 missed last two"])


if __name__ == "__main__":
    main(Path(sys.argv[1]))
