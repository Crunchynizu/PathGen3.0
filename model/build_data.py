"""Build student-disjoint train/test CSVs from the full Junyi 2015 log and skill_map.csv.

    python build_data.py <junyi data dir> <output dir>

Same split rule as the groupmate's build_junyi_csvs.py (sorted user ids, shuffled with
seed 42, first 20% of students held out for testing), but with no row cap: every mapped
answer of every student is kept. Answers are ordered by student, then time_done, then
position in the source log.
"""

from __future__ import annotations

import csv
import json
import random
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAP = HERE / "skill_map.csv"
SEED = 42
TEST_SHARE = 0.20
SKILLS = [f"S{i}" for i in range(1, 8)]
COLUMNS = ["user_id", "skill_code", "time_done", "y"]


def load_map(exercise_table: Path) -> dict[tuple[str, str], str]:
    with exercise_table.open(encoding="utf-8-sig", newline="") as f:
        names = {row["name"] for row in csv.DictReader(f)}
    mapping = {}
    with MAP.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == ["exercise", "problem_type", "skill_code"], reader.fieldnames
        for row in reader:
            key = row["exercise"].strip(), row["problem_type"].strip()
            assert key[0] in names, f"unknown exercise {key[0]}"
            assert row["skill_code"] in SKILLS, row
            assert key not in mapping, f"duplicate {key}"
            mapping[key] = row["skill_code"]
    return mapping


def main(data_dir: Path, out_dir: Path) -> None:
    mapping = load_map(data_dir / "junyi_Exercise_table.csv")
    rows = []
    per_exercise = Counter()
    with (data_dir / "junyi_ProblemLog_original.csv").open(encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        header = next(reader)
        ui, ei, pi, ti, ci = (header.index(c) for c in ("user_id", "exercise", "problem_type", "time_done", "correct"))
        for line, row in enumerate(reader, start=2):
            exercise, problem_type = row[ei], row[pi]
            skill = mapping.get((exercise, problem_type), mapping.get((exercise, "")))
            if skill is None:
                continue
            label = row[ci].strip().lower()
            assert label in ("true", "false"), f"bad label at line {line}"
            rows.append((row[ui], skill, int(row[ti]), 1 if label == "true" else 0, line))
            per_exercise[f"{exercise}|{problem_type}" if (exercise, problem_type) in mapping else exercise] += 1

    users = sorted({r[0] for r in rows})
    random.Random(SEED).shuffle(users)
    test_users = set(users[: int(len(users) * TEST_SHARE)])
    rows.sort(key=lambda r: (r[0], r[2], r[4]))

    out_dir.mkdir(parents=True, exist_ok=True)
    counts = {}
    for name, keep in (("train", lambda u: u not in test_users), ("test", lambda u: u in test_users)):
        part = [r for r in rows if keep(r[0])]
        with (out_dir / f"{name}.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(COLUMNS)
            w.writerows(r[:4] for r in part)
        counts[name] = {
            "answers": len(part),
            "students": len({r[0] for r in part}),
            "answers_by_skill": dict(sorted(Counter(r[1] for r in part).items())),
            "correct_rate": round(sum(r[3] for r in part) / len(part), 4),
        }
        print(name, counts[name])
    summary = {"seed": SEED, "test_share": TEST_SHARE, "answers_by_exercise": dict(per_exercise), **counts}
    (out_dir / "build_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main(Path(sys.argv[1]), Path(sys.argv[2]))
