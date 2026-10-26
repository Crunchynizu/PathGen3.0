"""Final acceptance procedure (new_q_learning_training.md section 12, steps 1-5), with the
v2 review fixes, v3's Lesson 2 part rows, and v4's changes (see trainer.py): one-skill parts
for every lesson, and per-skill BKT numbers from skill_params.json.
"""

import json
import os
from dataclasses import replace
from multiprocessing import Pool

from export import (EXPORT_GAP, TIE_MARGIN, choice, consolidate, contract_problems, declare,
                    export_rows, policy_check)
from trainer import (ADDITIONAL_ACTIONS, ALPHA_EXPONENT, FAMILIES, GAMMA, PART,
                     REGULAR_ACTIONS, SKILL_PARAMS, SKILL_PARAMS_PATH, distinct_params,
                     reachable_training_keys, td_target, train_seed)

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "output")
V3_TABLE = os.path.join(HERE, "..", "q-learning-test-v3", "output", "q_table.json")

BURDEN_WEIGHTS = [0.02, 0.04, 0.06, 0.08, 0.10, 0.12]
COMPLETION_UTILITIES = [0.02, 0.04, 0.06, 0.08, 0.10]
CALIBRATION_SEEDS = list(range(1, 11))          # the guide does not list calibration seeds
TRAINING_SEEDS = [11, 23, 37, 41, 53, 67, 71, 83, 97, 101]
EPISODES = 75000                                 # fix: 50,000 cannot reach 500 updates per cell
EPISODE_STEPS = [75000, 150000, 300000]          # section 8: run more if not converged
MIN_VISITS = 500
DRIFT_LIMIT = 0.01
HINT_PROBABILITY = 0.5
HINT_SWEEP = [0.0, 1.0]
# design choices re-run as sensitivities; none of them is installed
SENSITIVITIES = {
    "near miss split (3 of 6 = n)": replace(PART, name="part-near-miss", pass_results=("p", "n", "f"), near_miss=True),
    "pass 3 of 6": replace(PART, pass_correct=3),
    "foundational 6 items": replace(PART, foundational_items=6),
}
SHORT = {"progress": "progress", "additional_exercise": "additional",
         "foundational_exercise": "foundational"}
GRID = [(b, c) for b in BURDEN_WEIGHTS for c in COMPLETION_UTILITIES]


def run_job(job):
    seed, params, episodes, family = job
    return train_seed(seed, params, episodes, family=family)


def keys_where(family, pred):
    return [k for k in family.keys() if pred(*k.strip("()").split(", "))]


def check_gates(tables, info, rankings, family):
    """Section 7 gates, evaluated on the declared policy (after the tie and pass rules)."""
    g1_fail = [k for k in keys_where(family, lambda w, a, p: set(p) == {"p"})
               if choice(rankings[k], ADDITIONAL_ACTIONS) != "progress"
               or choice(rankings[k], REGULAR_ACTIONS) == "foundational_exercise"]
    g2_fail = []
    for k in keys_where(family, lambda w, a, p: w == "strong"):
        c = choice(rankings[k], REGULAR_ACTIONS)
        if c != "progress" and not all(t[k][c] > t[k]["progress"] for t in tables):
            g2_fail.append(k)
    g3 = any(choice(rankings[k], REGULAR_ACTIONS) != "progress"
             for k in keys_where(family, lambda w, a, p: w == "np" and set(p) != {"p"}))
    # fix: gate 4 applies to rows with a clear margin; sub-0.01 rows belong to the tie rule
    g4_fail = [k for k in family.keys()
               if info[k]["top_two_margin"] >= TIE_MARGIN and not info[k]["seed_stable"]]
    g5 = td_target(reward=0.2, terminated=True, max_next=99.0) == 0.2
    gates = {"gate1_all_passed_rows": not g1_fail, "gate2_strong_progress": not g2_fail,
             "gate3_some_np_row_supports": g3, "gate4_clear_rows_seed_stable": not g4_fail,
             "gate5_terminal_test": g5}
    return gates, {"gate1_failing_rows": g1_fail, "gate2_failing_rows": g2_fail,
                   "gate4_failing_rows": g4_fail}


def evaluate(runs, family):
    tables = [r["Q"] for r in runs]
    median, info = consolidate(tables, family)
    rankings, source = declare(median, info, family)
    gates, detail = check_gates(tables, info, rankings, family)
    return {"passes": all(gates.values()), **gates, **detail,
            "tie_rule_rows": sum(s.startswith("tie rule") for s in source.values()),
            "min_visits_per_seed": min(min(r["visits"].values()) for r in runs)}


def calibrate(pool, families):
    """Per weight pair: gate results for each family, and whether all of them pass."""
    jobs = [(s, {"burden_weight": b, "completion_utility": c, "hint_probability": HINT_PROBABILITY},
             EPISODES, f) for f in families for b, c in GRID for s in CALIBRATION_SEEDS]
    results = iter(pool.map(run_job, jobs))
    n = len(CALIBRATION_SEEDS)
    per_family = {f.name: [evaluate([next(results) for _ in range(n)], f) for _ in GRID]
                  for f in families}
    return [{"burden_weight": b, "completion_utility": c,
             "passes_all_gates": all(per_family[f.name][i]["passes"] for f in families),
             **{f.name: per_family[f.name][i] for f in families}}
            for i, (b, c) in enumerate(GRID)]


def masks_policy(rankings):
    return {k: (choice(r, REGULAR_ACTIONS), choice(r, ADDITIONAL_ACTIONS)) for k, r in rankings.items()}


def train_production(pool, params, episodes, family):
    return pool.map(run_job, [(s, params, episodes, family) for s in TRAINING_SEEDS])


def convergence(runs, family):
    """Section 8 check, on what is exported: the consolidated median table and its
    declared policy, 80% checkpoint vs end."""
    final_median, final_info = consolidate([r["Q"] for r in runs], family)
    ckpt_median, ckpt_info = consolidate([r["checkpoint_80"] for r in runs], family)
    drift = max(abs(final_median[k][a] - ckpt_median[k][a])
                for k in final_median for a in final_median[k])
    final_policy = masks_policy(declare(final_median, final_info, family)[0])
    ckpt_policy = masks_policy(declare(ckpt_median, ckpt_info, family)[0])
    changed = sorted(k for k in final_policy if final_policy[k] != ckpt_policy[k])
    return drift, changed


def policy_of(runs, family):
    m, i = consolidate([r["Q"] for r in runs], family)
    return masks_policy(declare(m, i, family)[0])


def skill_params_meta():
    with open(SKILL_PARAMS_PATH) as f:
        raw = json.load(f)
    return {"dataset": raw.get("dataset"), "method": raw.get("method"),
            "distinct_parameter_sets": len(distinct_params(SKILL_PARAMS)),
            "skills": {code: vars(bkt) for code, bkt in SKILL_PARAMS.items()}}


def main():
    os.makedirs(os.path.join(OUT, "raw"), exist_ok=True)
    if os.path.exists(os.path.join(OUT, "q_table.json")):
        os.remove(os.path.join(OUT, "q_table.json"))   # never leave an earlier run's artifact

    with Pool() as pool:
        print(f"Calibration: {len(GRID)} pairs x {len(CALIBRATION_SEEDS)} seeds x {EPISODES} episodes, "
              f"{len(SKILL_PARAMS)} skills, {len(distinct_params(SKILL_PARAMS))} distinct BKT parameter set(s)...")
        sweep = calibrate(pool, FAMILIES)
        with open(os.path.join(OUT, "calibration_report.json"), "w") as f:
            json.dump(sweep, f, indent=2)
        passing = sorted((s for s in sweep if s["passes_all_gates"]),
                         key=lambda s: (s["burden_weight"], s["completion_utility"]))
        print(f"Passing all gates: {len(passing)} / {len(sweep)}")
        if not passing:
            write_failure_report(sweep)
            print("No candidate passes; no artifact written. See output/training_report.md")
            return
        chosen = passing[0]
        params = {"burden_weight": chosen["burden_weight"],
                  "completion_utility": chosen["completion_utility"],
                  "hint_probability": HINT_PROBABILITY}
        print(f"Selected: burden {params['burden_weight']}, completion {params['completion_utility']}")

        history = []
        for episodes in EPISODE_STEPS:
            runs = {f.name: train_production(pool, params, episodes, f) for f in FAMILIES}
            step_result = {"episodes": episodes}
            for f in FAMILIES:
                drift, changed = convergence(runs[f.name], f)
                step_result[f.name] = {"median_drift": drift, "policy_changes": changed}
                print(f"Production {episodes} episodes, {f.name}: median drift {drift:.4f}, "
                      f"declared policy changes {len(changed)}")
            history.append(step_result)
            if all(step_result[f.name]["median_drift"] <= DRIFT_LIMIT
                   and not step_result[f.name]["policy_changes"] for f in FAMILIES):
                break
        converged = all(history[-1][f.name]["median_drift"] <= DRIFT_LIMIT
                        and not history[-1][f.name]["policy_changes"] for f in FAMILIES)

        hint_runs = {(h, f.name): train_production(pool, dict(params, hint_probability=h), episodes, f)
                     for h in HINT_SWEEP for f in FAMILIES}

        print("Sensitivities...")
        sens_sweep = calibrate(pool, list(SENSITIVITIES.values()))
        sensitivity = {}
        for label, fam in SENSITIVITIES.items():
            sruns = train_production(pool, params, episodes, fam)
            m, i = consolidate([r["Q"] for r in sruns], fam)
            r, s = declare(m, i, fam)
            sensitivity[label] = {
                "family": fam,
                "calibration_passes": sum(x[fam.name]["passes"] for x in sens_sweep),
                "at_selected": evaluate(sruns, fam),
                "policy": masks_policy(r),
                "median": m, "info": i, "source": s, "rankings": r,
            }

    for f in FAMILIES:
        for seed, r in zip(TRAINING_SEEDS, runs[f.name]):
            with open(os.path.join(OUT, "raw", f"{f.name}_seed_{seed}.json"), "w") as fh:
                json.dump(r, fh, indent=2)

    median, info, rankings, source, tables = {}, {}, {}, {}, {}
    for f in FAMILIES:
        tables[f.name] = [r["Q"] for r in runs[f.name]]
        m, i = consolidate(tables[f.name], f)
        r, s = declare(m, i, f)
        median.update(m), info.update(i), rankings.update(r), source.update(s)
    q_values = export_rows(median, rankings)

    all_visits = [r["visits"] for f in FAMILIES for r in runs[f.name]]
    min_visits = min(min(v.values()) for v in all_visits)
    under = sorted({k for v in all_visits for k, n in v.items() if n < MIN_VISITS})

    base_policy = masks_policy(rankings)
    hint_sensitive = set()
    for h in HINT_SWEEP:
        for f in FAMILIES:
            p = policy_of(hint_runs[(h, f.name)], f)
            hint_sensitive |= {k for k in p if p[k] != base_policy[k]}
    hint_sensitive = sorted(hint_sensitive)

    final_gates = {f.name: check_gates(tables[f.name], info, rankings, f) for f in FAMILIES}
    tie_rows = [k for k, s in source.items() if s.startswith("tie rule")]
    pass_rule_rows = [k for k, s in source.items() if "pass rule" in s]
    moves_on_rows = [k for k, s in source.items() if "moves-on rule" in s]
    artifact = {
        "_meta": {
            "policy_version": "Q-LEARNING-V1",
            "artifact_kind": "externally_trained",
            "trainer_revision": "terminal-aware-v4-one-skill-parts",
            "trained_episodes_per_seed": episodes,
            "training_seeds": TRAINING_SEEDS,
            "calibration_seeds": CALIBRATION_SEEDS,
            "gamma": GAMMA,
            "alpha_schedule": f"1/n^{ALPHA_EXPONENT}, n = updates to the shared state-action cell",
            "behavior_policy": "uniform_allowed_actions",
            "reward": {"type": "mastery_gain_minus_burden_plus_completion",
                       "burden_weight": float(params["burden_weight"]),
                       "completion_utility": float(params["completion_utility"])},
            "skill_params": skill_params_meta(),
            "state_families": {
                f.name: {"skills_per_exercise": f.n_skills,
                         "items_per_skill": f.additional_items,
                         "pass_rule": f"{f.pass_correct} of {f.additional_items} correct",
                         "foundational_items_per_failed_skill": f.foundational_items,
                         "passed_exercise_moves_on": f.pass_moves_on,
                         "rows": f.keys()} for f in FAMILIES},
            "declared_policy_rules": ["median raw Q order",
                                      "section 9 practical-tie rule on unstable rows",
                                      "passed rows (p): progress ranks above foundational_exercise",
                                      "a passed part (p) always chooses progress"],
            "export_transform": f"per-row affine to [0.05, 0.95], then ranked actions "
                                f"separated by at least {EXPORT_GAP} after rounding",
            "foundational_hint_probability": HINT_PROBABILITY,
            "reachable_training_rows": len(reachable_training_keys()),
            "practical_tie_rows": tie_rows,
            "pass_rule_rows": pass_rule_rows,
            "moves_on_rule_rows": moves_on_rows,
            "hint_sensitive_rows": hint_sensitive,
            "converged": converged,
        },
        "q_values": q_values,
    }
    with open(os.path.join(OUT, "q_table.json"), "w") as f:
        json.dump(artifact, f, indent=2)

    problems = contract_problems(artifact)
    mismatches = policy_check(rankings, q_values)
    v3 = compare_v3(q_values, params)
    write_report(sweep, chosen, median, info, rankings, source, q_values, hint_sensitive,
                 min_visits, under, history, converged, problems, mismatches, final_gates,
                 sensitivity, v3)

    print(f"Coverage: min visits per (context, state, action) = {min_visits} "
          f"({'PASS' if not under else f'FAIL, {len(under)} cells < {MIN_VISITS}'})")
    print(f"Converged: {converged} at {episodes} episodes")
    print(f"Rows by source: learned {sum(s.startswith('learned') for s in source.values())}, "
          f"tie rule {len(tie_rows)}, pass rule {len(pass_rule_rows)}, moves-on rule {len(moves_on_rows)}   Hint-sensitive: {len(hint_sensitive)}")
    print(f"Export reproduces declared policy under both masks: {'yes' if not mismatches else mismatches}")
    print(f"Part rows vs v3 batch rows: {v3['summary']}")
    for label, s in sensitivity.items():
        print(f"Sensitivity '{label}': calibration passes {s['calibration_passes']}/{len(GRID)}, "
              f"gates at selected weights {'pass' if s['at_selected']['passes'] else 'FAIL'}")
    print(f"Artifact contract: {'PASS' if not problems else 'FAIL'}")
    for p in problems:
        print("  -", p)
    print("Saved: output/q_table.json, output/calibration_report.json, output/training_report.md")


def compare_v3(q_values, params):
    """v3's batch rows are the same one-skill family. With one set of BKT numbers (the
    placeholders) and the same weights, v4 must reproduce them exactly."""
    try:
        with open(V3_TABLE) as f:
            v3 = json.load(f)
    except OSError:
        return {"summary": "v3 artifact not found", "diff_rows": [], "choice_diff": [], "same_weights": None}
    keys = PART.keys()
    diff = [k for k in keys if v3["q_values"].get(k) != q_values.get(k)]
    choice_diff = [k for k in keys if any(
        choice(sorted(m, key=lambda a: (-v3["q_values"][k][a], a)), m)
        != choice(sorted(m, key=lambda a: (-q_values[k][a], a)), m)
        for m in (REGULAR_ACTIONS, ADDITIONAL_ACTIONS))]
    w = v3["_meta"]["reward"]
    same_weights = (w["burden_weight"], w["completion_utility"]) == (params["burden_weight"], params["completion_utility"])
    summary = ("identical" if not diff else
               f"{len(diff)} rows differ in value, {len(choice_diff)} differ in chosen action")
    return {"summary": summary, "diff_rows": diff, "choice_diff": choice_diff,
            "same_weights": same_weights, "v3_weights": w}


def gate_cell(r):
    if r["passes"]:
        return "ok"
    failed = [label for g, label in (("gate1_all_passed_rows", "g1"), ("gate2_strong_progress", "g2"),
                                     ("gate3_some_np_row_supports", "g3"),
                                     ("gate4_clear_rows_seed_stable", "g4")) if not r[g]]
    return "FAIL " + ",".join(failed)


def calibration_table(sweep):
    L = ["| burden | completion | gates | tie-rule rows |", "|---|---|---|---|"]
    for s in sweep:
        L.append(f"| {s['burden_weight']} | {s['completion_utility']} | {gate_cell(s['part'])} | "
                 f"{s['part']['tie_rule_rows']} |")
    return L


def write_failure_report(sweep):
    L = ["# Training report (q-learning-test-v4)", "",
         "**Acceptance: FAIL.** No weight pair passes the gates, so no artifact was written.", "",
         "## Calibration", ""] + calibration_table(sweep)
    with open(os.path.join(OUT, "training_report.md"), "w") as f:
        f.write("\n".join(L) + "\n")


def state_table(keys, median, info, source, rankings):
    L = ["| state | progress | additional | foundational | margin | seeds (P/A/F) | decided by | after regular | after additional |",
         "|---|---|---|---|---|---|---|---|---|"]
    for k in keys:
        m, cnt = median[k], info[k]["chosen_action_count"]
        L.append(f"| {k} | {m['progress']:.4f} | {m['additional_exercise']:.4f} | "
                 f"{m['foundational_exercise']:.4f} | {info[k]['top_two_margin']:.4f} | "
                 f"{cnt['progress']}/{cnt['additional_exercise']}/{cnt['foundational_exercise']} | "
                 f"{source[k]} | {SHORT[choice(rankings[k], REGULAR_ACTIONS)]} | "
                 f"{SHORT[choice(rankings[k], ADDITIONAL_ACTIONS)]} |")
    return L


def write_report(sweep, chosen, median, info, rankings, source, q_values, hint_sensitive,
                 min_visits, under, history, converged, problems, mismatches, final_gates,
                 sensitivity, v3):
    n = len(sweep)
    passing = sum(s["passes_all_gates"] for s in sweep)
    b, c = chosen["burden_weight"], chosen["completion_utility"]
    final = history[-1]
    status = "PASS" if (passing and not under and converged and not problems and not mismatches) else "FAIL"
    tie_rows = [k for k, s in source.items() if s.startswith("tie rule")]
    keys = PART.keys()
    policy = masks_policy({k: rankings[k] for k in keys})
    meta = skill_params_meta()
    learned_rows = [k for k in keys if source[k] in ("learned", "tie rule")]

    L = ["# Training report (q-learning-test-v4: one-skill lesson parts)", "",
         "Built on `q-learning-test-v3` (all review fixes kept). Two changes:", "",
         "1. **Every lesson is taught in one-skill parts** (instructor decision 2026-10-16). Only "
         "v3's one-skill family remains, renamed `part`; v3's two-skill `pair` rows for Lessons 1 "
         "and 3 are removed. The artifact has 6 rows: np/dev/strong x p/f.",
         "2. **Each skill has its own BKT numbers**, read from `skill_params.json`, the hand-over "
         "format of the Junyi model. Each training episode simulates one skill's numbers.", "",
         "## Summary", "",
         f"**Acceptance: {status}.** {passing} of {n} weight pairs pass the gates. Selected: burden "
         f"{b}, completion {c} (the smallest passing pair). Coverage "
         f"{'passes' if not under else 'fails'} (minimum {min_visits} updates per cell). Training "
         f"{'converged' if converged else 'did NOT converge'} at {final['episodes']:,} episodes per seed. "
         f"The {len(q_values)}-row `q_table.json` {'passes' if not problems else 'fails'} the contract "
         f"and {'reproduces' if not mismatches else 'does NOT reproduce'} the declared policy under both masks.", "",
         f"**Part rows vs v3's batch rows: {v3['summary']}.**"
         + (" With one set of BKT numbers and the same weights, v4 is v3's one-skill trainer "
            "unchanged, so the refactor did not move the policy." if v3["summary"] == "identical" else
            (" Expected, because the BKT numbers or weights differ from v3's." if not v3.get("same_weights")
             or meta["distinct_parameter_sets"] > 1 else " Unexpected: investigate before installing.")), "",
         "## BKT numbers used", "",
         f"Source: {meta['dataset']}", "",
         f"Method: {meta['method']}. Distinct parameter sets: {meta['distinct_parameter_sets']}.", "",
         "| skill | P(L0) | P(T) | P(G) | P(S) |", "|---|---|---|---|---|"]
    for code, p in meta["skills"].items():
        L.append(f"| {code} | {p['p_l0']:.3f} | {p['p_t']:.3f} | {p['p_g']:.3f} | {p['p_s']:.3f} |")
    L += ["", "P(L0) is not used in training (episodes start from sampled mastery in each band); "
          "PathGen uses it as each student's starting mastery.", "",
          "## Policy", "",
          f"Burden {b}, completion {c}, {final['episodes']:,} episodes, 10 seeds.", ""]
    L += state_table(keys, median, info, source, rankings)
    L += ["", f"**What Q-learning decides here.** {len(learned_rows)} of {len(keys)} rows are set by "
          f"training ({', '.join(learned_rows)}); the passed rows follow the declared moves-on rule "
          "agreed 2026-10-03. With one skill per part, the agent's real choice is what to do after a "
          "failed exercise. The near-miss sensitivity below tests a richer state for that choice.", "",
          "## Sensitivities (not installed)", "",
          "Re-run at the selected weights. \"changed\" lists shared rows whose choice differs from "
          "the policy above.", "",
          "| variant | weight pairs passing | gates at selected weights | choices (after regular / after additional) | changed |",
          "|---|---|---|---|---|"]
    for label, s in sensitivity.items():
        fam_keys = s["family"].keys()
        changed = [k for k in fam_keys if k in policy and s["policy"][k] != policy[k]]
        choices = "; ".join(f"{k}: {SHORT[s['policy'][k][0]]}/{SHORT[s['policy'][k][1]]}" for k in fam_keys)
        L.append(f"| {label} | {s['calibration_passes']} / {n} | {gate_cell(s['at_selected'])} | "
                 f"{choices} | {', '.join(changed) or 'none'} |")
    near = next((s for s in sensitivity.values() if s["family"].near_miss), None)
    if near:
        L += ["", "### Near-miss split", "",
              "A fail becomes `n` (one short of passing, 3 of 6) or `f` (0-2 of 6). Full table:", ""]
        L += state_table(near["family"].keys(), near["median"], near["info"], near["source"], near["rankings"])
    L += ["", "## Convergence", ""]
    for h in history:
        for f in FAMILIES:
            r = h[f.name]
            L.append(f"- {h['episodes']:,} episodes: median change {r['median_drift']:.4f}, "
                     f"declared choices changed in {len(r['policy_changes'])} rows"
                     + (f" ({', '.join(r['policy_changes'])})" if r["policy_changes"] else ""))
    L += ["", "## Gates on the production policy", ""]
    for name, (gates, detail) in final_gates.items():
        bad = [g for g, ok in gates.items() if not ok]
        L.append(f"- {name}: {'all pass' if not bad else 'FAIL ' + ', '.join(bad)}")
    hint_list = ", ".join(f"{k} margin {info[k]['top_two_margin']:.4f}" for k in hint_sensitive)
    L += ["", f"Hint sweep (0.0 / 1.0): {len(hint_sensitive)} rows flagged"
          + (f" ({hint_list})" if hint_sensitive else "") + ".", "",
          f"Rows decided by the tie rule: {len(tie_rows)}"
          + (f" ({', '.join(tie_rows)})" if tie_rows else "") + ".", "",
          "## How PathGen uses this artifact", "",
          f"- Copy `output/q_table.json` to `apps/adaptive/q_table.json` ({len(q_values)} rows). "
          "The app's loader requires exactly the 6 part rows, and `_state_for_session` expects "
          "one skill per lesson part (both in place since 2026-10-19).",
          "- `skill_params.json` must hold the same numbers as `content_source/manifest.json` "
          "(6 decimals). They come from `model/output/skill_params_final.json`; after a "
          "refit, replace the file, rerun, and update both.", "",
          "## Calibration", ""]
    L += calibration_table(sweep)
    L += ["", f"Selected (smallest burden, then smallest completion, among passing pairs): "
          f"burden {b}, completion {c}.", ""]
    with open(os.path.join(OUT, "training_report.md"), "w") as f:
        f.write("\n".join(L))


if __name__ == "__main__":
    main()
