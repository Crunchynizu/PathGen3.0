# Q-learning trainer (q-learning-test-v4)

PathGen's Q-learning trainer. It builds on `q-learning-test-v3`, which stays in the main thesis folder outside this repo (`run_all.py` compares against it only when that folder sits next to this one). Two changes from v3:

1. **One-skill parts for every lesson** (instructor decision 2026-10-16). Lessons 1 and 3 are split like Lesson 2. Each part ends in a 6-item exercise on one skill, which passes with 4 of 6. Only v3's one-skill family remains, renamed "part"; the two-skill "pair" family is gone.
2. **Each skill has its own BKT numbers**, read from `skill_params.json`. Each training episode draws one skill's numbers to simulate the student.

With one skill, weakest band = average band, so the artifact has 6 rows: `(np, np, p)` … `(strong, strong, f)`. A student who passes a part always moves on (the declared rule agreed 2026-10-03), so training decides the three fail rows.

## BKT numbers

`skill_params.json` holds the Junyi fit from `../model` (variant "final", rounded to 6 decimals, the same numbers as the app's `content_source/manifest.json`). The borrowed numbers it replaced (0.30 / 0.09 / 0.10 / 0.09 for every skill) are kept in `skill_params_placeholder.json`, and the run made with them is in `output_placeholder/`. Both runs pick the same action in all 6 rows; only the values differ.

## Run

```
python run_all.py        # calibration, production run, hint sweep, sensitivities, export (about 10 minutes)
python test_trainer.py   # trainer and export tests
```

Standard library only.

## Outputs

| Path | What it is |
|---|---|
| `output/q_table.json` | The 6-row artifact, copied to `pathgen3.0app/apps/adaptive/q_table.json`. Written only if a weight pair passes the gates. |
| `output/training_report.md` | Summary, BKT numbers used, policy, sensitivities, convergence, gates, calibration |
| `output/calibration_report.json` | Every weight pair with its gate results |
| `output/raw/part_seed_*.json` | Raw per-seed Q tables, visit counts, 80% checkpoints |
