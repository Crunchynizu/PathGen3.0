# Junyi BKT fit for PathGen

This folder fits PathGen's BKT numbers (P(L0), P(T), P(G), P(S) for skills S1–S7) on the Junyi Academy 2015 practice log. These numbers replace the borrowed ones PathGen used before (0.30 / 0.09 / 0.10 / 0.09 for every skill, from Hawkins et al. 2013). Fitted 2026-10-25.

The numbers PathGen uses are in **`output/skill_params_final.json`**. They are also copied to `../trainer/skill_params.json` (trainer) and `../pathgen3.0app/content_source/manifest.json` (app), rounded to 6 decimals.

## Files

| File | What it is |
|---|---|
| `skill_map.csv` | Which Junyi exercises count as which PathGen skill |
| `build_data.py` | Reads the Junyi log, keeps mapped answers, splits students into train and test |
| `fit_bkt.py` | Fits BKT per skill, scores the test students once, writes the outputs |
| `output/skill_params_<version>.json` | Fitted numbers for each version (format read by the v4 trainer) |
| `output/metrics.csv` | Every skill × version: numbers, test scores, and the PathGen band after typical answer patterns |
| `output/build_summary.json` | Answer and student counts, file hashes |

## How to rerun

Needs Python 3 with numpy, scipy and scikit-learn (a venv is at `C:\Users\User\junyi\venv`). The Junyi files are large, so they stay outside OneDrive.

```
python build_data.py C:\Users\User\junyi\data C:\Users\User\junyi\bkt     # about 2 minutes
python fit_bkt.py C:\Users\User\junyi\bkt                                  # about 2 minutes
```

Source files (Junyi Academy Math Practicing Log, January 2015 release, from the EduData/USTC mirror):

| File | SHA-256 |
|---|---|
| `junyi_ProblemLog_original.csv` | `a7c99ede1f9b19648fdcd953b6ca0b0282bd31f2f913bd9d26b23aa9fcb36a25` |
| `junyi_Exercise_table.csv` | `13292cc2c809985abbacedaba434e39aeb02a7fcb2a32f17b60c4d3f4d769546` |

## 1. Skill map

Rule: **keep exercises in Junyi's negative-numbers topic** (`topic = absolute-value`, `area = algebra` in the exercise table), **and drop any whose numbers are not integers.**

| Skill | Junyi exercises | Answers |
|---|---|---|
| S1 Identify integers, opposites, absolute value | absolute_value, absolute_values_meaning, definition_opposite_number, comparing_absolute_values | 248,371 |
| S2 Add and subtract integers | adding_negative_numbers, adding_and_subtracting_negative_numbers, number_line_3, number_line_4 | 611,783 |
| S3 Multiply integers | multiplying_and_dividing_negative_numbers, `problem_type` = multiplying | 41,765 |
| S4 Order of operations | operations_with_negative_numbers | 26,052 |
| S5 Represent, compare, order | ordering_negative_numbers | 143,838 |
| S6 Signed-change situations | negative_number_word_problems | 98,527 |
| S7 Divide integers | multiplying_and_dividing_negative_numbers, `problem_type` = dividing | 41,838 |

Left out:

- `number_line_0.5` and `number_line_0.7`: steps of 0.5 and 0.7, so decimals.
- `order_of_operations` and `integer_arithmetic`: Junyi files them under elementary arithmetic (`area = arithmetic`), so they are whole numbers.
- `absolute_value_add_sub`: mixes S1 and S2.
- Exercises with no answers in the log.

## 2. Data

- **Label:** `y = 1` if Junyi's `correct` field is true, meaning right on the first attempt with no hint.
- **Order:** answers are ordered by student, then `time_done`.
- **Split by student:** student IDs are shuffled with seed 42 and 20% of students are held out for testing. No student is in both sets. Every mapped answer is used (no row cap).

| | Answers | Students | Correct |
|---|---|---|---|
| Train | 960,605 | 23,008 | 80.3% |
| Test | 251,569 | 5,752 | 80.4% |

## 3. Method

Standard four-parameter BKT, fitted separately for each skill. For a student with mastery probability $p$ before an answer:

$$P(\text{correct}) = p\,(1-P(S)) + (1-p)\,P(G)$$

$$p' = \begin{cases} \dfrac{p\,(1-P(S))}{p\,(1-P(S)) + (1-p)\,P(G)} & \text{if correct} \\[2ex] \dfrac{p\,P(S)}{p\,P(S) + (1-p)\,(1-P(G))} & \text{if wrong} \end{cases}
\qquad
p_{\text{next}} = p' + (1-p')\,P(T)$$

Each student starts each skill at $p = P(L0)$.

**Fitting.**

- The parameters maximise the log-likelihood of every training answer, $\sum \big[y \log P(\text{correct}) + (1-y)\log(1-P(\text{correct}))\big]$, using scipy's L-BFGS-B, which accepts limits on each parameter directly.
- Every fit runs from 6 starting points. All six reached the same answer for every final fit, except S3 (5 of 6); the best one is kept.
- On simulated students with known numbers, the fit recovers them closely.

**Numerical detail.** The code tracks $1-p$, the chance the student has *not* mastered the skill, instead of $p$. After a long run of correct answers, $p$ rounds to exactly 1.0, and then wrong answers can no longer lower it. Whether that rounding happens flips with tiny parameter changes, and the optimiser could not handle that. The formulas are the same.

**Scoring.** Each version predicts every test answer from that student's earlier answers on the same skill. Reported:

- **AUC:** how well it separates right from wrong answers; 0.5 = chance.
- **Brier:** mean squared error of the predicted probability; lower is better.

## 4. Versions compared

All limits were chosen before looking at test results.

| Version | Limits | Why |
|---|---|---|
| borrowed | none (fixed 0.30 / 0.09 / 0.10 / 0.09) | What PathGen used before |
| unconstrained | none | Best fit to Junyi |
| bounded (option A) | P(G) ≤ 0.3, P(S) ≤ 0.1 | Usual limits in the BKT literature (Baker, Corbett & Aleven 2008) |
| fixed_guess (option B) | P(G) = 0.25 | Blind-guess rate on PathGen's 4-choice questions |
| **final** | option A + P(T) ≤ 0.3 | **What PathGen uses** (group decision 2026-10-25) |

## 5. Results

**Why limits were needed.** Without them, P(G) came out between 0.36 and 0.73 for 5 of 7 skills. That would mean a student who has *not* learned a skill answers correctly more often than not, which is impossible to square with 4-choice questions (blind guessing is 0.25). It happens because nearly everyone answers Junyi items correctly (80%). In PathGen, the unconstrained numbers would make S1 harsh: 5 of 6 right would end at "developing" and 4 of 6 at "not proficient".

**Why P(T) ≤ 0.3.** Ordering negative numbers (S5) is 92% correct on Junyi. Under option A it fits P(T) = 0.74, so even 2 of 6 right ends "strong". The cap only affects S5; every other skill fits below 0.22.

**Final numbers and test scores:**

| Skill | P(L0) | P(T) | P(G) | P(S) | AUC borrowed → final | Brier borrowed → final |
|---|---|---|---|---|---|---|
| S1 | 0.827 | 0.066 | 0.300 | 0.100 | 0.544 → 0.588 | 0.118 → 0.109 |
| S2 | 0.580 | 0.033 | 0.300 | 0.100 | 0.573 → 0.623 | 0.188 → 0.175 |
| S3 | 0.891 | 0.197 | 0.300 | 0.081 | 0.582 → 0.597 | 0.136 → 0.091 |
| S4 | 0.151 | 0.033 | 0.284 | 0.100 | 0.784 → 0.785 | 0.199 → 0.194 |
| S5 | 0.698 | 0.300 | 0.300 | 0.058 | 0.624 → 0.625 | 0.095 → 0.072 |
| S6 | 0.176 | 0.080 | 0.300 | 0.100 | 0.681 → 0.687 | 0.208 → 0.195 |
| S7 | 0.849 | 0.165 | 0.300 | 0.100 | 0.584 → 0.601 | 0.164 → 0.125 |

The final numbers beat the borrowed ones on Brier for all 7 skills, and on AUC for 4 (level on S4, S5, S6). The unconstrained version predicts Junyi better still (for example, S1 AUC 0.708), but behaves badly in PathGen (see above). That trade-off is the reason for the limits. Every version is in `output/metrics.csv`.

**P(L0) is Junyi's own estimate.** S1, S3 and S7 start high (0.83–0.89) because Junyi students are often reviewing. PathGen's pre-test updates every skill before any lesson, so the band after the pre-test is what matters. The pre-test has 1–10 questions per skill (S6 has 1, S4 has 10). Starting from Junyi's value or from 0.30 gives the same band after the pre-test, except three cases: S3 or S7 with 2 of 4 right ("developing" vs "not proficient"), and S6 with its one question right ("not proficient" vs "developing").

**What the final numbers do in PathGen** (band after one 6-question lesson part; np = not proficient < 0.50 ≤ dev < 0.80 ≤ strong):

| Skill | 6/6 | 5/6 | 4/6, missed first two | 4/6, missed last two | 3/6 |
|---|---|---|---|---|---|
| S1 | strong | strong | strong | strong | np |
| S2 | strong | strong | strong | dev | np |
| S3 | strong | strong | strong | strong | dev |
| S4 | strong | strong | strong | **np** | np |
| S5 | strong | strong | strong | strong | np |
| S6 | strong | strong | strong | **np** | np |
| S7 | strong | strong | strong | strong | dev |

These rows start from Junyi's P(L0), not from a pre-test result; `output/metrics.csv` has the exact values.

## 6. Limitations

- **Population.** Junyi students are Taiwanese learners in 2015, answering mostly typed questions; PathGen students are Grade 7 learners on 4-choice questions. Carrying the numbers over is an assumption. P(L0) in particular reflects Junyi's population.
- **Limits.** Most skills sit at the limits (P(G) = 0.3 for 6 of 7, P(S) = 0.1 for 5 of 7), so those values come from the chosen limits more than from the data. The limits follow the BKT literature and the 4-choice format, and were set before the test results were seen.
- **Order effect.** Because BKT weights recent answers more, 4 of 6 right ends "not proficient" on S4 and S6 if the two misses are the last questions. A student can pass a part (4 of 6) and still be labelled "not proficient". The Q-learning state includes both the pass result and the band.
- **S6 pre-test.** S6 has one pre-test question, so even a right answer leaves it "not proficient" (0.39).
- **Future work.** Once PathGen has real users, their pre-test and lesson answers can be used to refit P(L0), or all four numbers, on PathGen's own population.

## Related

- `JUNYI_MODEL_REVIEW.md` (main thesis folder, outside this repo): review of the groupmate's first fit and DKT model, which led to this refit.
- `pathgen_model-main/` (main thesis folder, outside this repo): the groupmate's pipeline (pyBKT on an 80k/20k sample; DKT). DKT stays as a reference model in the thesis, not part of PathGen.
