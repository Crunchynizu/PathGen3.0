import json
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.adaptive import q_learning


class QLearningTests(SimpleTestCase):
    def tearDown(self):
        q_learning.load_q_table.cache_clear()

    def test_decide_returns_argmax_when_all_actions_available(self):
        row = {
            "progress": 0.1,
            "additional_exercise": 0.7,
            "foundational_exercise": 0.2,
        }
        with patch.object(q_learning, "load_q_table", return_value={"(np, dev, pf)": row}):
            result = q_learning.decide("np", "dev", "pf", q_learning.ACTIONS)
        self.assertEqual(result, ("additional_exercise", "q_learning_argmax"))

    def test_decide_masks_unavailable_actions(self):
        row = {
            "progress": 0.1,
            "additional_exercise": 0.9,
            "foundational_exercise": 0.4,
        }
        with patch.object(q_learning, "load_q_table", return_value={"(np, dev, pf)": row}):
            result = q_learning.decide(
                "np",
                "dev",
                "pf",
                ["progress", "foundational_exercise"],
            )
        self.assertEqual(result, ("foundational_exercise", "q_learning_argmax"))

    def test_decide_falls_back_when_state_is_missing(self):
        with patch.object(q_learning, "load_q_table", return_value={}):
            result = q_learning.decide("np", "dev", "pf", q_learning.ACTIONS)
        self.assertEqual(result, ("progress", "q_learning_missing_fallback"))

    def test_decide_falls_back_when_q_table_is_missing(self):
        with tempfile.TemporaryDirectory() as directory:
            missing = Path(directory) / "missing.json"
            with patch.object(q_learning, "Q_TABLE_PATH", missing):
                q_learning.load_q_table.cache_clear()
                result = q_learning.decide("np", "dev", "pf", q_learning.ACTIONS)
        self.assertEqual(result, ("progress", "q_learning_missing_fallback"))

    def test_decide_falls_back_when_all_actions_are_masked(self):
        row = {
            "progress": 0.1,
            "additional_exercise": 0.7,
            "foundational_exercise": 0.2,
        }
        with patch.object(q_learning, "load_q_table", return_value={"(np, dev, pf)": row}):
            result = q_learning.decide("np", "dev", "pf", [])
        self.assertEqual(result, ("progress", "q_learning_missing_fallback"))

    def test_decide_uses_alphabetical_tie_break(self):
        row = {
            "progress": 0.5,
            "additional_exercise": 0.5,
            "foundational_exercise": 0.5,
        }
        with patch.object(q_learning, "load_q_table", return_value={"(np, dev, pf)": row}):
            result = q_learning.decide("np", "dev", "pf", q_learning.ACTIONS)
        self.assertEqual(result, ("additional_exercise", "q_learning_argmax"))

    def test_valid_artifact_loads_all_24_rows(self):
        q_learning.load_q_table.cache_clear()
        self.assertEqual(len(q_learning.load_q_table()), 24)

    def test_invalid_policy_version_falls_back(self):
        artifact = json.loads(q_learning.Q_TABLE_PATH.read_text(encoding="utf-8"))
        artifact["_meta"]["policy_version"] = "INVALID"
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "q_table.json"
            path.write_text(json.dumps(artifact), encoding="utf-8")
            with patch.object(q_learning, "Q_TABLE_PATH", path):
                q_learning.load_q_table.cache_clear()
                result = q_learning.decide("np", "np", "pp", q_learning.ACTIONS)
        self.assertEqual(result, ("progress", "q_learning_missing_fallback"))
