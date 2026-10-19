import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

from django.conf import settings


CONTENT_SOURCE_ROOT = Path(settings.BASE_DIR) / "content_source"
SCHEMA_ROOT = Path(__file__).resolve().parent / "schemas"
CHOICE_LABELS = ["A", "B", "C", "D"]
SET_TYPES = ("regular", "additional", "foundational", "activity", "prepost")
# The curriculum is data: skills, lessons and questions come from the JSON files, and these
# rules check their shape instead of fixed codes or totals.
EXERCISE_ITEMS = 6        # regular and additional exercises, split evenly over the lesson's skills
FOUNDATIONAL_ITEMS = 3    # one foundational set per skill
EXERCISE_BLOOM = Counter({"LOTS": 4, "HOTS": 2})
FOUNDATIONAL_BLOOM = Counter({"LOTS": 2, "HOTS": 1})
ACTIVITY_HOTS_SHARE = 0.4
BKT_FIELDS = ("p_l0", "p_t", "p_g", "p_s")
# The pre/post-test is the study instrument, so it stays fixed.
PREPOST_CODES = [f"PP-{i:02d}" for i in range(1, 31)]
SCORING_POLICY = {
    "code": "SCORING-V3",
    "description": (
        "A skill passes with at least two-thirds of its questions correct: 4 of 6 in a lesson "
        "part's exercise, 2 of 3 in foundational work."
    ),
    "correct_required": {"3": 2, "6": 4},
}


class CurriculumSourceError(ValueError):
    pass


def load_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CurriculumSourceError(f"Cannot read valid JSON from {path}: {exc}") from exc


def sha256(path):
    digest = hashlib.sha256()
    try:
        with path.open("rb") as source:
            for chunk in iter(lambda: source.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise CurriculumSourceError(f"Cannot read source file {path}: {exc}") from exc
    return digest.hexdigest()


def load_curriculum_source(root=None):
    root = Path(root or CONTENT_SOURCE_ROOT)
    lessons = sorted(
        (load_json(path) for path in (root / "lessons").glob("lesson_*.json")),
        key=lambda document: document["lesson"].get("lesson_order", 0),
    )
    return {
        "root": root,
        "manifest": load_json(root / "manifest.json"),
        "media": load_json(root / "media_manifest.json"),
        "lessons": lessons,
        "activity": load_json(root / "activity.json"),
        "prepost": load_json(root / "pretest_posttest.json"),
    }


def iter_question_sets(source):
    for lesson in source["lessons"]:
        yield from lesson["question_sets"]
    yield source["activity"]["question_set"]
    yield source["prepost"]["question_set"]


def iter_questions(source):
    for question_set in iter_question_sets(source):
        for question in question_set["questions"]:
            yield question_set, question


def _require(condition, message):
    if not condition:
        raise CurriculumSourceError(message)


def _validate_schema_files():
    expected = {
        "lesson.schema.json",
        "manifest.schema.json",
        "media_manifest.schema.json",
        "question.schema.json",
        "question_set.schema.json",
    }
    actual = {path.name for path in SCHEMA_ROOT.glob("*.json")}
    _require(expected <= actual, f"Missing JSON schemas: {sorted(expected - actual)}")
    for path in SCHEMA_ROOT.glob("*.json"):
        schema = load_json(path)
        _require(schema.get("$schema") == "https://json-schema.org/draft/2020-12/schema", f"{path.name} must use JSON Schema draft 2020-12")


def _validate_png(path):
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise CurriculumSourceError(f"Cannot read prompt figure {path}: {exc}") from exc
    _require(data.startswith(b"\x89PNG\r\n\x1a\n"), f"Prompt figure is not PNG: {path}")
    _require(len(data) >= 26, f"Prompt figure is truncated: {path}")
    width, height = struct.unpack(">II", data[16:24])
    _require(width > 0 and height > 0, f"Prompt figure has invalid dimensions: {path}")


def _is_probability(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return False
    return 0.0 <= value <= 1.0


def _has_cycle(graph):
    state = {}

    def visit(node):
        if state.get(node) == "done":
            return False
        if state.get(node) == "active":
            return True
        state[node] = "active"
        if any(visit(parent) for parent in graph.get(node, [])):
            return True
        state[node] = "done"
        return False

    return any(visit(node) for node in graph)


def _validate_skills(manifest):
    """Skill codes and prerequisite graph from manifest.json."""
    skills = manifest.get("skills")
    _require(isinstance(skills, list) and skills, "manifest.json must list at least one skill")
    codes = [skill.get("code") for skill in skills]
    _require(all(isinstance(code, str) and code.strip() for code in codes), "Every skill needs a code")
    duplicates = sorted(code for code, total in Counter(codes).items() if total > 1)
    _require(not duplicates, f"Duplicate skill codes: {duplicates}")
    prerequisites = {}
    for skill in skills:
        code = skill["code"]
        _require(str(skill.get("name", "")).strip(), f"{code} name is empty")
        for field in BKT_FIELDS:
            _require(_is_probability(skill.get(field)), f"{code} {field} must be a probability between 0 and 1")
        parents = skill.get("prerequisites", [])
        _require(
            isinstance(parents, list) and len(set(parents)) == len(parents)
            and all(parent in codes and parent != code for parent in parents),
            f"{code} prerequisites must name other skills, each once",
        )
        junyi = skill.get("junyi_exercises", [])
        _require(
            isinstance(junyi, list) and len(set(junyi)) == len(junyi)
            and all(isinstance(name, str) and name.strip() for name in junyi),
            f"{code} junyi_exercises must be distinct Junyi exercise names",
        )
        prerequisites[code] = parents
    _require(not _has_cycle(prerequisites), "Skill prerequisites must not form a loop")
    return codes, prerequisites


def _validate_lessons(lessons, skill_codes, prerequisites):
    """Lesson order, units and parts, and which lesson teaches each skill."""
    records = [document["lesson"] for document in lessons]
    _require(records, "At least one lesson is required")
    codes = [record.get("code") for record in records]
    _require(all(codes) and len(set(codes)) == len(codes), "Lesson codes must be unique and nonblank")
    _require(
        [record.get("lesson_order") for record in records] == list(range(1, len(records) + 1)),
        f"Lesson order must run 1 through {len(records)} with no gaps",
    )

    # Records of one unit sit together; a unit is either one whole lesson or parts 1..k.
    units = []
    for record in records:
        if units and units[-1][0] == record.get("unit_number"):
            units[-1][1].append(record)
        else:
            units.append((record.get("unit_number"), [record]))
    _require(
        [number for number, _ in units] == list(range(1, len(units) + 1)),
        "Units must run 1 through N in lesson order, with each unit's parts together",
    )
    for number, members in units:
        parts = [member.get("part_number") for member in members]
        _require(
            parts == [None] or parts == list(range(1, len(members) + 1)),
            f"Unit {number} must be one whole lesson or parts numbered 1 through {len(members)}",
        )
        _require(len({member.get("unit_title") for member in members}) == 1, f"Unit {number} parts must share one unit title")

    lesson_skills = {}
    taught_in = {}
    for record in records:
        code = record["code"]
        skills = record.get("skill_codes", [])
        _require(skills and len(set(skills)) == len(skills), f"{code} must teach at least one skill, each once")
        _require(set(skills) <= set(skill_codes), f"{code} has an unknown skill")
        _require(EXERCISE_ITEMS % len(skills) == 0, f"{code} has {len(skills)} skills; its {EXERCISE_ITEMS} exercise questions must split evenly")
        _require(bool(record.get("unit_title", "").strip()), f"{code} unit title is empty")
        _require(bool(record.get("content", {}).get("source_text", "").strip()), f"{code} source text is empty")
        lesson_skills[code] = skills
        for skill in skills:
            taught_in.setdefault(skill, []).append(record["lesson_order"])
    _require(
        sorted(taught_in) == sorted(skill_codes) and all(len(orders) == 1 for orders in taught_in.values()),
        "Every skill must belong to exactly one lesson",
    )
    for skill, parents in prerequisites.items():
        for parent in parents:
            _require(taught_in[parent][0] <= taught_in[skill][0], f"{skill} needs {parent}, which is taught in a later lesson")
    return lesson_skills, len(units)


def _validate_videos(source, media):
    videos = media.get("videos", [])
    codes = [video.get("code") for video in videos]
    _require(all(codes) and len(set(codes)) == len(codes), "Video codes must be unique and nonblank")
    for video in videos:
        transcript_path = source["root"] / video["transcript_file"]
        try:
            transcript = transcript_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise CurriculumSourceError(f"Cannot read transcript {transcript_path}: {exc}") from exc
        _require(transcript.strip(), f"{video['code']} transcript is empty")
        start, end = video.get("segment_start_seconds"), video.get("segment_end_seconds")
        if start is not None and end is not None:
            _require(0 <= start < end, f"{video['code']} segment must start before it ends")
    by_code = dict(zip(codes, videos))
    for document in source["lessons"]:
        for block in document["lesson"].get("content", {}).get("blocks", []):
            if block.get("type") != "video":
                continue
            _require(block.get("video_code") in by_code, f"{document['lesson']['code']} video block has unknown video {block.get('video_code')}")
            start, end = block.get("segment_start_seconds"), block.get("segment_end_seconds")
            if start is not None and end is not None:
                _require(0 <= start < end, f"{document['lesson']['code']} video segment must start before it ends")
    return by_code


def _validate_question(question, *, skill_codes, videos, seen_codes):
    code = question.get("code")
    _require(code and code not in seen_codes, f"Duplicate or blank question code: {code}")
    seen_codes.add(code)
    choices = question.get("choices", [])
    _require(len(choices) == 4, f"{code} must have exactly four choices")
    _require([choice.get("label") for choice in choices] == CHOICE_LABELS, f"{code} choices must be ordered A-D")
    _require(all(isinstance(choice.get("text"), str) and choice["text"].strip() for choice in choices), f"{code} choices must be nonblank text")
    _require(all("image_asset" not in choice for choice in choices), f"{code} has a forbidden choice image_asset")
    correct = [choice["label"] for choice in choices if choice.get("is_correct") is True]
    _require(correct == [question.get("correct_answer")], f"{code} must have exactly one matching keyed answer")
    _require(question.get("skill_code") in skill_codes, f"{code} has invalid skill")
    _require(question.get("prompt", "").strip(), f"{code} prompt is blank")
    _require(question.get("presentation_type") in {"text", "figure", "video"}, f"{code} has invalid presentation_type")
    if question.get("presentation_type") == "figure":
        _require(bool(question.get("image_asset")), f"{code} figure is missing image_asset")
    else:
        _require(question.get("image_asset") is None, f"{code} non-figure has image_asset")
    video_code = question.get("video_code")
    if video_code is not None:
        _require(video_code in videos, f"{code} has unknown video {video_code}")
        pause = question.get("video_pause_seconds")
        start = videos[video_code].get("segment_start_seconds")
        end = videos[video_code].get("segment_end_seconds")
        if pause is not None and start is not None and end is not None:
            _require(start <= pause <= end, f"{code} pauses at {pause}s, outside its video segment {start}-{end}s")


def validate_curriculum_source(root=None):
    _validate_schema_files()
    source = load_curriculum_source(root)
    manifest = source["manifest"]
    media = source["media"]

    _require(manifest.get("schema_version") == 1, "manifest.json schema_version must be 1")
    _require(manifest.get("scoring_policy") == SCORING_POLICY, "SCORING-V3 must require 2 of 3 and 4 of 6")
    skill_codes, prerequisites = _validate_skills(manifest)

    for source_name, entry in manifest.get("source_files", {}).items():
        path = (Path(settings.BASE_DIR) / entry["path"]).resolve()
        actual_hash = sha256(path)
        _require(actual_hash == entry["sha256"], f"SHA-256 mismatch for {source_name}: expected {entry['sha256']}, got {actual_hash}")
    prepost_hash = manifest["source_files"]["pretest_posttest_pdf"]["sha256"]
    _require(manifest.get("pretest_posttest_sha256") == prepost_hash, "manifest pre/post SHA-256 values disagree")
    _require(source["prepost"].get("source_pdf_sha256") == prepost_hash, "pretest_posttest.json SHA-256 does not match manifest")

    lesson_skills, unit_count = _validate_lessons(source["lessons"], skill_codes, prerequisites)
    videos = _validate_videos(source, media)

    questions = []
    counts = Counter()
    seen_codes = set()
    exercise_sets = Counter()
    foundational_skills = []
    for question_set in iter_question_sets(source):
        set_type = question_set.get("set_type")
        set_code = question_set.get("code")
        _require(set_type in SET_TYPES, f"Unknown set type {set_type}")
        set_questions = question_set.get("questions", [])
        if set_type in {"regular", "additional"}:
            lesson_code = question_set.get("lesson_code")
            _require(lesson_code in lesson_skills and question_set.get("skill_code") is None, f"{set_code} has invalid lesson/skill context")
            _require(len(set_questions) == EXERCISE_ITEMS, f"{set_code} must have {EXERCISE_ITEMS} questions")
            skills = lesson_skills[lesson_code]
            per_skill = Counter(question.get("skill_code") for question in set_questions)
            _require(per_skill == Counter({code: EXERCISE_ITEMS // len(skills) for code in skills}), f"{set_code} must split its {EXERCISE_ITEMS} questions evenly over {skills}")
            exercise_sets[(set_type, lesson_code)] += 1
        elif set_type == "foundational":
            skill_code = question_set.get("skill_code")
            _require(question_set.get("lesson_code") is None and skill_code in skill_codes, f"{set_code} has invalid foundational context")
            _require(len(set_questions) == FOUNDATIONAL_ITEMS, f"{set_code} must have {FOUNDATIONAL_ITEMS} questions")
            _require(all(question.get("skill_code") == skill_code for question in set_questions), f"{set_code} questions must all target {skill_code}")
            foundational_skills.append(skill_code)
        else:
            _require(question_set.get("lesson_code") is None and question_set.get("skill_code") is None, f"{set_code} must not have lesson/skill context")

        bloom = Counter(question.get("bloom_band") for question in set_questions)
        if set_type in {"regular", "additional"}:
            _require(bloom == EXERCISE_BLOOM, f"{set_code} must be 4 LOTS / 2 HOTS")
        elif set_type == "foundational":
            _require(bloom == FOUNDATIONAL_BLOOM, f"{set_code} must be 2 LOTS / 1 HOTS")
        elif set_type == "activity":
            hots = round(ACTIVITY_HOTS_SHARE * len(set_questions))
            _require(
                bloom == Counter({"LOTS": len(set_questions) - hots, "HOTS": hots}),
                f"Activity must be {len(set_questions) - hots} LOTS / {hots} HOTS",
            )

        for question in set_questions:
            _validate_question(question, skill_codes=skill_codes, videos=videos, seen_codes=seen_codes)
            counts[set_type] += 1
            questions.append(question)

    for lesson_code in lesson_skills:
        for set_type in ("regular", "additional"):
            _require(exercise_sets[(set_type, lesson_code)] == 1, f"{lesson_code} needs exactly one {set_type} exercise")
    _require(sorted(foundational_skills) == sorted(skill_codes), "Every skill needs exactly one foundational set")

    activity_questions = source["activity"]["question_set"]["questions"]
    missing = sorted(set(skill_codes) - {question["skill_code"] for question in activity_questions})
    _require(not missing, f"The activity must cover every skill; missing {missing}")

    prepost_questions = source["prepost"]["question_set"]["questions"]
    _require([question["code"] for question in prepost_questions] == PREPOST_CODES, "Pre/post order must be PP-01 through PP-30")
    _require(all(question["presentation_type"] == "text" and question["image_asset"] is None for question in prepost_questions), "Pre/post must be text-only")
    rewrite = next((item for item in manifest.get("prepost_rewrites", []) if item.get("code") == "PP-13"), None)
    _require(rewrite is not None, "manifest.json must record the PP-13 rewrite")
    pp13 = prepost_questions[12]
    _require(pp13["prompt"] == rewrite["new_prompt"], "PP-13 prompt does not match manifest rewrite")
    _require([f"{choice['label']}. {choice['text']}" for choice in pp13["choices"]] == rewrite["new_choices"], "PP-13 choices do not match manifest rewrite")
    _require(pp13["correct_answer"] == rewrite["new_key"], "PP-13 key does not match manifest rewrite")

    actual_counts = {
        "lessons": len(source["lessons"]),
        "lesson_units": unit_count,
        "skills": len(skill_codes),
        "questions_total": len(questions),
        **{set_type: counts[set_type] for set_type in SET_TYPES},
    }
    for name, actual in actual_counts.items():
        _require(manifest.get("counts", {}).get(name) == actual, f"manifest.json counts.{name} must be {actual}")

    figure_map = {figure.get("question_code"): figure for figure in media.get("figures", [])}
    figure_questions = [question for question in questions if question.get("presentation_type") == "figure"]
    _require(set(figure_map) == {question["code"] for question in figure_questions}, "media_manifest figure inventory does not match figure questions")
    for question in figure_questions:
        figure = figure_map[question["code"]]
        _require(figure.get("path") == question["image_asset"], f"{question['code']} figure path mismatch")
        _validate_png(Path(settings.BASE_DIR) / "static" / figure["path"])

    avatar_dir = Path(settings.BASE_DIR) / "static" / "avatar"
    logo_dir = Path(settings.BASE_DIR) / "static" / "logo"
    _require({path.name for path in avatar_dir.glob("*.png")} == {"student_avatar.png", "teacher_avatar.png", "admin_avatar.png"}, "static/avatar must contain exactly the three role avatars")
    _require({path.name for path in logo_dir.glob("*.png")} == {"pathgen.png"}, "static/logo must contain pathgen.png")
    _require(not (Path(settings.BASE_DIR) / "static" / "pretest_posttest").exists(), "static/pretest_posttest must not exist")

    return {
        **actual_counts,
        "figures": len(figure_questions),
        "videos": len(videos),
        "pretest_posttest_sha256": prepost_hash,
    }
