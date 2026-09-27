import hashlib
import json
import struct
from collections import Counter
from pathlib import Path

from django.conf import settings


CONTENT_SOURCE_ROOT = Path(settings.BASE_DIR) / "content_source"
SCHEMA_ROOT = Path(__file__).resolve().parent / "schemas"
CHOICE_LABELS = ["A", "B", "C", "D"]
EXPECTED_COUNTS = {
    "regular": 18,
    "additional": 18,
    "foundational": 18,
    "activity": 10,
    "prepost": 30,
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
    lessons = [load_json(root / "lessons" / f"lesson_{number}.json") for number in range(1, 4)]
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


def validate_curriculum_source(root=None):
    _validate_schema_files()
    source = load_curriculum_source(root)
    manifest = source["manifest"]
    media = source["media"]
    source_root = source["root"]

    _require(manifest.get("schema_version") == 1, "manifest.json schema_version must be 1")
    _require(manifest.get("scoring_policy") == {"code": "SCORING-V2", "correct_required": 2, "questions_per_skill": 3}, "SCORING-V2 must require 2 of 3")
    _require([skill.get("code") for skill in manifest.get("skills", [])] == [f"S{i}" for i in range(1, 7)], "Skill codes must be S1 through S6")

    for source_name, entry in manifest.get("source_files", {}).items():
        path = (Path(settings.BASE_DIR) / entry["path"]).resolve()
        actual_hash = sha256(path)
        _require(actual_hash == entry["sha256"], f"SHA-256 mismatch for {source_name}: expected {entry['sha256']}, got {actual_hash}")
    prepost_hash = manifest["source_files"]["pretest_posttest_pdf"]["sha256"]
    _require(manifest.get("pretest_posttest_sha256") == prepost_hash, "manifest pre/post SHA-256 values disagree")
    _require(source["prepost"].get("source_pdf_sha256") == prepost_hash, "pretest_posttest.json SHA-256 does not match manifest")

    lesson_codes = [lesson["lesson"].get("code") for lesson in source["lessons"]]
    lesson_orders = [lesson["lesson"].get("lesson_order") for lesson in source["lessons"]]
    _require(lesson_codes == ["L1", "L2", "L3"], "Lesson codes must be L1, L2, L3")
    _require(lesson_orders == [1, 2, 3], "Lesson order must be 1, 2, 3")
    for lesson in source["lessons"]:
        lesson_record = lesson["lesson"]
        _require(len(lesson_record.get("skill_codes", [])) == 2, f"{lesson_record.get('code')} must have two skills")
        _require(bool(lesson_record.get("content", {}).get("source_text", "").strip()), f"{lesson_record.get('code')} source text is empty")

    questions = []
    counts = Counter()
    seen_codes = set()
    for question_set in iter_question_sets(source):
        set_type = question_set.get("set_type")
        _require(set_type in EXPECTED_COUNTS, f"Unknown set type {set_type}")
        if set_type in {"regular", "additional"}:
            _require(question_set.get("lesson_code") in {"L1", "L2", "L3"} and question_set.get("skill_code") is None, f"{question_set.get('code')} has invalid lesson/skill context")
            _require(len(question_set.get("questions", [])) == 6, f"{question_set.get('code')} must have 6 questions")
        elif set_type == "foundational":
            _require(question_set.get("lesson_code") is None and question_set.get("skill_code") in {f"S{i}" for i in range(1, 7)}, f"{question_set.get('code')} has invalid foundational context")
            _require(len(question_set.get("questions", [])) == 3, f"{question_set.get('code')} must have 3 questions")
        else:
            _require(question_set.get("lesson_code") is None and question_set.get("skill_code") is None, f"{question_set.get('code')} must not have lesson/skill context")

        bloom = Counter(question.get("bloom_band") for question in question_set.get("questions", []))
        if set_type in {"regular", "additional"}:
            _require(bloom == Counter({"LOTS": 4, "HOTS": 2}), f"{question_set.get('code')} must be 4 LOTS / 2 HOTS")
        elif set_type == "foundational":
            _require(bloom == Counter({"LOTS": 2, "HOTS": 1}), f"{question_set.get('code')} must be 2 LOTS / 1 HOTS")
        elif set_type == "activity":
            _require(bloom == Counter({"LOTS": 6, "HOTS": 4}), "Activity must be 6 LOTS / 4 HOTS")

        for question in question_set.get("questions", []):
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
            _require(question.get("skill_code") in {f"S{i}" for i in range(1, 7)}, f"{code} has invalid skill")
            _require(question.get("prompt", "").strip(), f"{code} prompt is blank")
            _require(question.get("presentation_type") in {"text", "figure", "video"}, f"{code} has invalid presentation_type")
            if question.get("presentation_type") == "figure":
                _require(bool(question.get("image_asset")), f"{code} figure is missing image_asset")
            else:
                _require(question.get("image_asset") is None, f"{code} non-figure has image_asset")
            counts[set_type] += 1
            questions.append(question)

    _require(dict(counts) == EXPECTED_COUNTS, f"Question counts mismatch: {dict(counts)}")
    _require(len(questions) == 94, f"Expected 94 questions, found {len(questions)}")
    _require(manifest.get("counts", {}).get("questions_total") == 94, "Manifest total must be 94")
    for set_type, expected in EXPECTED_COUNTS.items():
        _require(manifest.get("counts", {}).get(set_type) == expected, f"Manifest {set_type} count must be {expected}")

    prepost_questions = source["prepost"]["question_set"]["questions"]
    _require([question["code"] for question in prepost_questions] == [f"PP-{i:02d}" for i in range(1, 31)], "Pre/post order must be PP-01 through PP-30")
    _require(all(question["presentation_type"] == "text" and question["image_asset"] is None for question in prepost_questions), "Pre/post must be text-only")
    rewrite = next((item for item in manifest.get("prepost_rewrites", []) if item.get("code") == "PP-13"), None)
    _require(rewrite is not None, "manifest.json must record the PP-13 rewrite")
    pp13 = prepost_questions[12]
    _require(pp13["prompt"] == rewrite["new_prompt"], "PP-13 prompt does not match manifest rewrite")
    _require([f"{choice['label']}. {choice['text']}" for choice in pp13["choices"]] == rewrite["new_choices"], "PP-13 choices do not match manifest rewrite")
    _require(pp13["correct_answer"] == rewrite["new_key"], "PP-13 key does not match manifest rewrite")

    activity_questions = source["activity"]["question_set"]["questions"]
    _require(Counter(question["skill_code"] for question in activity_questions) == Counter({"S1": 2, "S2": 2, "S3": 2, "S4": 2, "S5": 1, "S6": 1}), "Activity skill distribution is invalid")

    figure_map = {figure.get("question_code"): figure for figure in media.get("figures", [])}
    figure_questions = [question for question in questions if question.get("presentation_type") == "figure"]
    _require(set(figure_map) == {question["code"] for question in figure_questions}, "media_manifest figure inventory does not match figure questions")
    for question in figure_questions:
        figure = figure_map[question["code"]]
        _require(figure.get("path") == question["image_asset"], f"{question['code']} figure path mismatch")
        _validate_png(Path(settings.BASE_DIR) / "static" / figure["path"])

    videos = media.get("videos", [])
    _require(len(videos) == 4, "media_manifest must contain four videos")
    for video in videos:
        transcript_path = source_root / video["transcript_file"]
        try:
            transcript = transcript_path.read_text(encoding="utf-8")
        except OSError as exc:
            raise CurriculumSourceError(f"Cannot read transcript {transcript_path}: {exc}") from exc
        _require(transcript.startswith("# TRANSCRIPT PLACEHOLDER — source not provided in lesson.pdf\n"), f"{video['code']} transcript placeholder header is invalid")

    avatar_dir = Path(settings.BASE_DIR) / "static" / "avatar"
    logo_dir = Path(settings.BASE_DIR) / "static" / "logo"
    _require({path.name for path in avatar_dir.glob("*.png")} == {"student_avatar.png", "teacher_avatar.png", "admin_avatar.png"}, "static/avatar must contain exactly the three role avatars")
    _require({path.name for path in logo_dir.glob("*.png")} == {"pathgen.png"}, "static/logo must contain pathgen.png")
    _require(not (Path(settings.BASE_DIR) / "static" / "pretest_posttest").exists(), "static/pretest_posttest must not exist")

    return {
        "lessons": 3,
        "skills": 6,
        "questions_total": len(questions),
        **dict(counts),
        "figures": len(figure_questions),
        "videos": len(videos),
        "pretest_posttest_sha256": prepost_hash,
    }
