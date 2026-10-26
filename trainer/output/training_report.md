# Training report (q-learning-test-v4: one-skill lesson parts)

Built on `q-learning-test-v3` (all review fixes kept). Two changes:

1. **Every lesson is taught in one-skill parts** (instructor decision 2026-10-16). Only v3's one-skill family remains, renamed `part`; v3's two-skill `pair` rows for Lessons 1 and 3 are removed. The artifact has 6 rows: np/dev/strong x p/f.
2. **Each skill has its own BKT numbers**, read from `skill_params.json`, the hand-over format of the Junyi model. Each training episode simulates one skill's numbers.

## Summary

**Acceptance: PASS.** 30 of 30 weight pairs pass the gates. Selected: burden 0.02, completion 0.02 (the smallest passing pair). Coverage passes (minimum 1939 updates per cell). Training converged at 75,000 episodes per seed. The 6-row `q_table.json` passes the contract and reproduces the declared policy under both masks.

**Part rows vs v3's batch rows: 3 rows differ in value, 0 differ in chosen action.** Expected, because the BKT numbers or weights differ from v3's.

## BKT numbers used

Source: Junyi Academy Math Practicing Log, January 2015 release (all mapped answers)

Method: standard BKT, maximum likelihood (L-BFGS-B, 6 starts), variant 'final'. Distinct parameter sets: 7.

| skill | P(L0) | P(T) | P(G) | P(S) |
|---|---|---|---|---|
| S1 | 0.827 | 0.066 | 0.300 | 0.100 |
| S2 | 0.580 | 0.033 | 0.300 | 0.100 |
| S3 | 0.891 | 0.197 | 0.300 | 0.081 |
| S4 | 0.151 | 0.033 | 0.284 | 0.100 |
| S5 | 0.698 | 0.300 | 0.300 | 0.058 |
| S6 | 0.177 | 0.080 | 0.300 | 0.100 |
| S7 | 0.849 | 0.165 | 0.300 | 0.100 |

P(L0) is not used in training (episodes start from sampled mastery in each band); PathGen uses it as each student's starting mastery.

## Policy

Burden 0.02, completion 0.02, 75,000 episodes, 10 seeds.

| state | progress | additional | foundational | margin | seeds (P/A/F) | decided by | after regular | after additional |
|---|---|---|---|---|---|---|---|---|
| (np, np, p) | 0.0200 | 0.4040 | 0.0200 | 0.3840 | 10/0/0 | learned + pass rule + moves-on rule | progress | progress |
| (np, np, f) | 0.0200 | 0.4033 | 0.2278 | 0.1756 | 0/10/0 | learned | additional | foundational |
| (dev, dev, p) | 0.0200 | 0.1809 | 0.0200 | 0.1609 | 10/0/0 | learned + pass rule + moves-on rule | progress | progress |
| (dev, dev, f) | 0.0200 | 0.1907 | 0.1184 | 0.0723 | 0/10/0 | learned | additional | foundational |
| (strong, strong, p) | 0.0200 | 0.0487 | 0.0200 | 0.0287 | 10/0/0 | learned + pass rule + moves-on rule | progress | progress |
| (strong, strong, f) | 0.0200 | 0.0464 | 0.0412 | 0.0052 | 0/10/0 | tie rule | foundational | foundational |

**What Q-learning decides here.** 3 of 6 rows are set by training ((np, np, f), (dev, dev, f), (strong, strong, f)); the passed rows follow the declared moves-on rule agreed 2026-10-03. With one skill per part, the agent's real choice is what to do after a failed exercise. The near-miss sensitivity below tests a richer state for that choice.

## Sensitivities (not installed)

Re-run at the selected weights. "changed" lists shared rows whose choice differs from the policy above.

| variant | weight pairs passing | gates at selected weights | choices (after regular / after additional) | changed |
|---|---|---|---|---|
| near miss split (3 of 6 = n) | 30 / 30 | ok | (np, np, p): progress/progress; (np, np, n): additional/foundational; (np, np, f): additional/foundational; (dev, dev, p): progress/progress; (dev, dev, n): additional/foundational; (dev, dev, f): additional/foundational; (strong, strong, p): progress/progress; (strong, strong, n): foundational/foundational; (strong, strong, f): foundational/foundational | none |
| pass 3 of 6 | 25 / 30 | ok | (np, np, p): progress/progress; (np, np, f): additional/foundational; (dev, dev, p): progress/progress; (dev, dev, f): additional/foundational; (strong, strong, p): progress/progress; (strong, strong, f): foundational/foundational | none |
| foundational 6 items | 25 / 30 | ok | (np, np, p): progress/progress; (np, np, f): additional/foundational; (dev, dev, p): progress/progress; (dev, dev, f): additional/foundational; (strong, strong, p): progress/progress; (strong, strong, f): additional/foundational | (strong, strong, f) |

### Near-miss split

A fail becomes `n` (one short of passing, 3 of 6) or `f` (0-2 of 6). Full table:

| state | progress | additional | foundational | margin | seeds (P/A/F) | decided by | after regular | after additional |
|---|---|---|---|---|---|---|---|---|
| (np, np, p) | 0.0200 | 0.4104 | 0.0200 | 0.3904 | 10/0/0 | learned + pass rule + moves-on rule | progress | progress |
| (np, np, n) | 0.0200 | 0.4073 | 0.2314 | 0.1759 | 0/10/0 | learned | additional | foundational |
| (np, np, f) | 0.0200 | 0.4079 | 0.2264 | 0.1815 | 0/10/0 | learned | additional | foundational |
| (dev, dev, p) | 0.0200 | 0.1844 | 0.0200 | 0.1644 | 10/0/0 | learned + pass rule + moves-on rule | progress | progress |
| (dev, dev, n) | 0.0200 | 0.1823 | 0.1204 | 0.0619 | 0/10/0 | learned | additional | foundational |
| (dev, dev, f) | 0.0200 | 0.1846 | 0.1193 | 0.0654 | 0/10/0 | learned | additional | foundational |
| (strong, strong, p) | 0.0200 | 0.0502 | 0.0200 | 0.0302 | 10/0/0 | learned + pass rule + moves-on rule | progress | progress |
| (strong, strong, n) | 0.0200 | 0.0480 | 0.0397 | 0.0083 | 0/9/1 | tie rule | foundational | foundational |
| (strong, strong, f) | 0.0200 | 0.0458 | 0.0407 | 0.0051 | 0/10/0 | tie rule | foundational | foundational |

## Convergence

- 75,000 episodes: median change 0.0031, declared choices changed in 0 rows

## Gates on the production policy

- part: all pass

Hint sweep (0.0 / 1.0): 0 rows flagged.

Rows decided by the tie rule: 1 ((strong, strong, f)).

## How PathGen uses this artifact

- Copy `output/q_table.json` to `apps/adaptive/q_table.json` (6 rows). The app's loader requires exactly the 6 part rows, and `_state_for_session` expects one skill per lesson part (both in place since 2026-10-19).
- `skill_params.json` must hold the same numbers as `content_source/manifest.json` (6 decimals). They come from `model/output/skill_params_final.json`; after a refit, replace the file, rerun, and update both.

## Calibration

| burden | completion | gates | tie-rule rows |
|---|---|---|---|
| 0.02 | 0.02 | ok | 1 |
| 0.02 | 0.04 | ok | 1 |
| 0.02 | 0.06 | ok | 0 |
| 0.02 | 0.08 | ok | 1 |
| 0.02 | 0.1 | ok | 1 |
| 0.04 | 0.02 | ok | 2 |
| 0.04 | 0.04 | ok | 1 |
| 0.04 | 0.06 | ok | 1 |
| 0.04 | 0.08 | ok | 1 |
| 0.04 | 0.1 | ok | 1 |
| 0.06 | 0.02 | ok | 2 |
| 0.06 | 0.04 | ok | 2 |
| 0.06 | 0.06 | ok | 2 |
| 0.06 | 0.08 | ok | 2 |
| 0.06 | 0.1 | ok | 2 |
| 0.08 | 0.02 | ok | 2 |
| 0.08 | 0.04 | ok | 2 |
| 0.08 | 0.06 | ok | 2 |
| 0.08 | 0.08 | ok | 3 |
| 0.08 | 0.1 | ok | 3 |
| 0.1 | 0.02 | ok | 1 |
| 0.1 | 0.04 | ok | 1 |
| 0.1 | 0.06 | ok | 2 |
| 0.1 | 0.08 | ok | 2 |
| 0.1 | 0.1 | ok | 1 |
| 0.12 | 0.02 | ok | 2 |
| 0.12 | 0.04 | ok | 2 |
| 0.12 | 0.06 | ok | 2 |
| 0.12 | 0.08 | ok | 1 |
| 0.12 | 0.1 | ok | 1 |

Selected (smallest burden, then smallest completion, among passing pairs): burden 0.02, completion 0.02.
