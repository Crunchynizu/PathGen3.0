"""The curriculum is data: a new lesson or skill needs JSON only, and broken content is refused."""

import copy
import json
import shutil
import tempfile
from pathlib import Path

from django.conf import settings
from django.test import SimpleTestCase

from apps.curriculum.source import CurriculumSourceError, validate_curriculum_source


SOURCE = Path(settings.BASE_DIR) / "content_source"


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path, data):
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


class CurriculumCopy:
    """A temporary copy of content_source that a test can change."""

    def __init__(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = Path(self._tmp.name) / "content_source"
        shutil.copytree(SOURCE, self.root)

    def close(self):
        self._tmp.cleanup()

    def load(self, name):
        return _read(self.root / name)

    def save(self, name, data):
        _write(self.root / name, data)

    def validate(self):
        return validate_curriculum_source(self.root)


def _question(template, *, code, skill, bloom):
    question = copy.deepcopy(template)
    question.update(code=code, skill_code=skill, bloom_band=bloom, presentation_type="text",
                    image_asset=None, image_alt=None, video_code=None, video_pause_seconds=None)
    return question


class DynamicCurriculumTests(SimpleTestCase):
    def setUp(self):
        self.copy = CurriculumCopy()
        self.addCleanup(self.copy.close)

    def assertRefused(self, message):
        with self.assertRaisesMessage(CurriculumSourceError, message):
            self.copy.validate()

    def test_current_curriculum_is_valid(self):
        summary = self.copy.validate()
        self.assertEqual((summary["skills"], summary["lessons"], summary["questions_total"]), (7, 5, 121))

    def test_new_lesson_with_new_skill_needs_only_json(self):
        manifest = self.copy.load("manifest.json")
        template = self.copy.load("lessons/lesson_3.json")
        question = template["question_sets"][0]["questions"][0]

        manifest["skills"].append({
            "code": "S8", "name": "Integer exponents", "description": "Evaluate powers of integers.",
            "p_l0": "0.300000", "p_t": "0.090000", "p_g": "0.100000", "p_s": "0.090000",
            "prerequisites": ["S3"], "junyi_exercises": ["exponents_1"],
        })
        blooms = ["LOTS"] * 4 + ["HOTS"] * 2
        lesson = copy.deepcopy(template)
        lesson["lesson"].update(code="L4", slug="integer-exponents", lesson_order=6, unit_number=4,
                                part_number=None, unit_title="Integer exponents", title="Integer exponents",
                                skill_codes=["S8"])
        lesson["question_sets"] = [
            {"code": "L4-R", "name": "Lesson 4 Regular Exercise", "set_type": "regular", "lesson_code": "L4", "skill_code": None,
             "questions": [_question(question, code=f"L4-R-S8-{i:02d}", skill="S8", bloom=b) for i, b in enumerate(blooms, 1)]},
            {"code": "L4-A", "name": "Lesson 4 Additional Exercise", "set_type": "additional", "lesson_code": "L4", "skill_code": None,
             "questions": [_question(question, code=f"L4-A-S8-{i:02d}", skill="S8", bloom=b) for i, b in enumerate(blooms, 1)]},
            {"code": "L4-F-S8", "name": "Foundational S8", "set_type": "foundational", "lesson_code": None, "skill_code": "S8",
             "questions": [_question(question, code=f"L4-F-S8-{i:02d}", skill="S8", bloom=b)
                           for i, b in enumerate(["LOTS", "LOTS", "HOTS"], 1)]},
        ]
        self.copy.save("lessons/lesson_4.json", lesson)

        activity = self.copy.load("activity.json")
        activity["question_set"]["questions"].append(_question(question, code="ACT-S8-01", skill="S8", bloom="LOTS"))
        self.copy.save("activity.json", activity)

        counts = manifest["counts"]
        counts.update(lessons=6, lesson_units=4, skills=8, regular=36, additional=36, foundational=24,
                      activity=11, questions_total=counts["questions_total"] + 16)
        self.copy.save("manifest.json", manifest)

        summary = self.copy.validate()
        self.assertEqual((summary["skills"], summary["lessons"], summary["lesson_units"]), (8, 6, 4))
        self.assertEqual(summary["activity"], 11)

    def test_prerequisite_loop_is_refused(self):
        manifest = self.copy.load("manifest.json")
        next(skill for skill in manifest["skills"] if skill["code"] == "S1")["prerequisites"] = ["S5"]
        self.copy.save("manifest.json", manifest)
        self.assertRefused("Skill prerequisites must not form a loop")

    def test_prerequisite_taught_later_is_refused(self):
        manifest = self.copy.load("manifest.json")
        for skill in manifest["skills"]:  # no other links, so only the order rule can fail
            skill["prerequisites"] = []
        next(skill for skill in manifest["skills"] if skill["code"] == "S5")["prerequisites"] = ["S4"]
        self.copy.save("manifest.json", manifest)
        self.assertRefused("S5 needs S4, which is taught in a later lesson")

    def test_unknown_prerequisite_is_refused(self):
        manifest = self.copy.load("manifest.json")
        manifest["skills"][0]["prerequisites"] = ["S99"]
        self.copy.save("manifest.json", manifest)
        self.assertRefused("S1 prerequisites must name other skills")

    def test_bad_bkt_number_is_refused(self):
        manifest = self.copy.load("manifest.json")
        manifest["skills"][0]["p_g"] = "1.5"
        self.copy.save("manifest.json", manifest)
        self.assertRefused("S1 p_g must be a probability between 0 and 1")

    def test_gap_in_lesson_order_is_refused(self):
        lesson = self.copy.load("lessons/lesson_3.json")
        lesson["lesson"]["lesson_order"] = 7
        self.copy.save("lessons/lesson_3.json", lesson)
        self.assertRefused("Lesson order must run 1 through 5 with no gaps")

    def test_unknown_video_is_refused(self):
        activity = self.copy.load("activity.json")
        cue = next(q for q in activity["question_set"]["questions"] if q.get("video_code"))
        cue["video_code"] = "VID-MISSING"
        self.copy.save("activity.json", activity)
        self.assertRefused(f"{cue['code']} has unknown video VID-MISSING")

    def test_video_pause_outside_segment_is_refused(self):
        activity = self.copy.load("activity.json")
        cue = next(q for q in activity["question_set"]["questions"] if q.get("video_code"))
        cue["video_pause_seconds"] = 5
        self.copy.save("activity.json", activity)
        self.assertRefused(f"{cue['code']} pauses at 5s, outside its video segment")

    def test_activity_must_cover_every_skill(self):
        activity = self.copy.load("activity.json")
        for question in activity["question_set"]["questions"]:
            if question["skill_code"] == "S6":
                question["skill_code"] = "S1"
        self.copy.save("activity.json", activity)
        self.assertRefused("The activity must cover every skill; missing ['S6']")

    def test_skill_without_foundational_set_is_refused(self):
        lesson = self.copy.load("lessons/lesson_3.json")
        lesson["question_sets"] = [s for s in lesson["question_sets"] if s.get("skill_code") != "S6"]
        self.copy.save("lessons/lesson_3.json", lesson)
        self.assertRefused("Every skill needs exactly one foundational set")

    def test_manifest_counts_must_match_content(self):
        manifest = self.copy.load("manifest.json")
        manifest["counts"]["regular"] = 99
        self.copy.save("manifest.json", manifest)
        self.assertRefused("manifest.json counts.regular must be 30")
