# Training report (q-learning-test-v4: one-skill lesson parts)

Built on `q-learning-test-v3` (all review fixes kept). Two changes:

1. **Every lesson is taught in one-skill parts** (instructor decision 2026-10-16). Only v3's one-skill family remains, renamed `part`; v3's two-skill `pair` rows for Lessons 1 and 3 are removed. The artifact has 6 rows: np/dev/strong x p/f.
2. **Each skill has its own BKT numbers**, read from `skill_params.json`, the hand-over format of the Junyi model. Each training episode simulates one skill's numbers.

## Summary

**Acceptance: PASS.** 30 of 30 weight pairs pass the gates. Selected: burden 0.02, completion 0.02 (the smallest passing pair). Coverage passes (minimum 1992 updates per cell). Training converged at 75,000 episodes per seed. The 6-row `q_table.json` passes the contract and reproduces the declared policy under both masks.

**Part rows vs v3's batch rows: identical.** With one set of BKT numbers and the same weights, v4 is v3's one-skill trainer unchanged, so the refactor did not move the policy.

## BKT numbers used

Source: PLACEHOLDER: not fitted yet. Every skill uses the BKT numbers PathGen uses today (Hawkins et al. 2013, ASSISTments), so v4 can be built and checked before the Junyi fit arrives.

Method: none. Distinct parameter sets: 1.

| skill | P(L0) | P(T) | P(G) | P(S) |
|---|---|---|---|---|
| S1 | 0.300 | 0.090 | 0.100 | 0.090 |
| S2 | 0.300 | 0.090 | 0.100 | 0.090 |
| S3 | 0.300 | 0.090 | 0.100 | 0.090 |
| S4 | 0.300 | 0.090 | 0.100 | 0.090 |
| S5 | 0.300 | 0.090 | 0.100 | 0.090 |
| S6 | 0.300 | 0.090 | 0.100 | 0.090 |
| S7 | 0.300 | 0.090 | 0.100 | 0.090 |

P(L0) is not used in training (episodes start from sampled mastery in each band); PathGen uses it as each student's starting mastery.

## Policy

Burden 0.02, completion 0.02, 75,000 episodes, 10 seeds.

| state | progress | additional | foundational | margin | seeds (P/A/F) | decided by | after regular | after additional |
|---|---|---|---|---|---|---|---|---|
| (np, np, p) | 0.0200 | 0.3669 | 0.0200 | 0.3469 | 10/0/0 | learned + pass rule + moves-on rule | progress | progress |
| (np, np, f) | 0.0200 | 0.3648 | 0.2019 | 0.1629 | 0/10/0 | learned | additional | foundational |
| (dev, dev, p) | 0.0200 | 0.1673 | 0.0200 | 0.1473 | 10/0/0 | learned + pass rule + moves-on rule | progress | progress |
| (dev, dev, f) | 0.0200 | 0.1692 | 0.0948 | 0.0744 | 0/10/0 | learned | additional | foundational |
| (strong, strong, p) | 0.0200 | 0.0423 | 0.0200 | 0.0223 | 10/0/0 | learned + pass rule + moves-on rule | progress | progress |
| (strong, strong, f) | 0.0200 | 0.0400 | 0.0337 | 0.0063 | 0/10/0 | tie rule | foundational | foundational |

**What Q-learning decides here.** 3 of 6 rows are set by training ((np, np, f), (dev, dev, f), (strong, strong, f)); the passed rows follow the declared moves-on rule agreed 2026-10-03. With one skill per part, the agent's real choice is what to do after a failed exercise. The near-miss sensitivity below tests a richer state for that choice.

## Sensitivities (not installed)

Re-run at the selected weights. "changed" lists shared rows whose choice differs from the policy above.

| variant | weight pairs passing | gates at selected weights | choices (after regular / after additional) | changed |
|---|---|---|---|---|
| near miss split (3 of 6 = n) | 30 / 30 | ok | (np, np, p): progress/progress; (np, np, n): additional/foundational; (np, np, f): additional/foundational; (dev, dev, p): progress/progress; (dev, dev, n): additional/foundational; (dev, dev, f): additional/foundational; (strong, strong, p): progress/progress; (strong, strong, n): foundational/foundational; (strong, strong, f): foundational/foundational | none |
| pass 3 of 6 | 30 / 30 | ok | (np, np, p): progress/progress; (np, np, f): additional/foundational; (dev, dev, p): progress/progress; (dev, dev, f): additional/foundational; (strong, strong, p): progress/progress; (strong, strong, f): foundational/foundational | none |
| foundational 6 items | 30 / 30 | ok | (np, np, p): progress/progress; (np, np, f): additional/foundational; (dev, dev, p): progress/progress; (dev, dev, f): additional/foundational; (strong, strong, p): progress/progress; (strong, strong, f): additional/foundational | (strong, strong, f) |

### Near-miss split

A fail becomes `n` (one short of passing, 3 of 6) or `f` (0-2 of 6). Full table:

| state | progress | additional | foundational | margin | seeds (P/A/F) | decided by | after regular | after additional |
|---|---|---|---|---|---|---|---|---|
| (np, np, p) | 0.0200 | 0.3675 | 0.0200 | 0.3475 | 10/0/0 | learned + pass rule + moves-on rule | progress | progress |
| (np, np, n) | 0.0200 | 0.3721 | 0.1942 | 0.1780 | 0/10/0 | learned | additional | foundational |
| (np, np, f) | 0.0200 | 0.3692 | 0.2043 | 0.1649 | 0/10/0 | learned | additional | foundational |
| (dev, dev, p) | 0.0200 | 0.1704 | 0.0200 | 0.1504 | 10/0/0 | learned + pass rule + moves-on rule | progress | progress |
| (dev, dev, n) | 0.0200 | 0.1708 | 0.0980 | 0.0729 | 0/10/0 | learned | additional | foundational |
| (dev, dev, f) | 0.0200 | 0.1675 | 0.0959 | 0.0716 | 0/10/0 | learned | additional | foundational |
| (strong, strong, p) | 0.0200 | 0.0434 | 0.0200 | 0.0234 | 10/0/0 | learned + pass rule + moves-on rule | progress | progress |
| (strong, strong, n) | 0.0200 | 0.0421 | 0.0329 | 0.0092 | 0/10/0 | tie rule | foundational | foundational |
| (strong, strong, f) | 0.0200 | 0.0429 | 0.0342 | 0.0087 | 0/10/0 | tie rule | foundational | foundational |

## Convergence

- 75,000 episodes: median change 0.0037, declared choices changed in 0 rows

## Gates on the production policy

- part: all pass

Hint sweep (0.0 / 1.0): 1 rows flagged ((strong, strong, f) margin 0.0063).

Rows decided by the tie rule: 1 ((strong, strong, f)).

## What PathGen needs to use this artifact

- `apps/adaptive/q_learning.py`: the loader requires at least 24 rows; this artifact has 6. It must require exactly the 6 part rows instead.
- `apps/adaptive/services.py` `_state_for_session`: one lesson skill only.
- Lessons 1 and 3 split into one-skill parts (1.1, 1.2, 3.1, 3.2), each with a 6-item regular and additional exercise, like Lesson 2's parts.
- When the Junyi fit arrives: replace `skill_params.json`, rerun, and copy the same numbers into `content_source/manifest.json`.

## Calibration

| burden | completion | gates | tie-rule rows |
|---|---|---|---|
| 0.02 | 0.02 | ok | 1 |
| 0.02 | 0.04 | ok | 1 |
| 0.02 | 0.06 | ok | 2 |
| 0.02 | 0.08 | ok | 1 |
| 0.02 | 0.1 | ok | 1 |
| 0.04 | 0.02 | ok | 2 |
| 0.04 | 0.04 | ok | 2 |
| 0.04 | 0.06 | ok | 2 |
| 0.04 | 0.08 | ok | 2 |
| 0.04 | 0.1 | ok | 2 |
| 0.06 | 0.02 | ok | 2 |
| 0.06 | 0.04 | ok | 2 |
| 0.06 | 0.06 | ok | 2 |
| 0.06 | 0.08 | ok | 2 |
| 0.06 | 0.1 | ok | 2 |
| 0.08 | 0.02 | ok | 1 |
| 0.08 | 0.04 | ok | 1 |
| 0.08 | 0.06 | ok | 1 |
| 0.08 | 0.08 | ok | 2 |
| 0.08 | 0.1 | ok | 2 |
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
