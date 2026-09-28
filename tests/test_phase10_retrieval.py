from unittest.mock import patch

from django.test import SimpleTestCase

from apps.feedback.retrieval.similarity import cosine_similarity, retrieve


def chunk(chunk_id, embedding):
    return {"chunk_id": chunk_id, "embedding": embedding}


class Phase10RetrievalTests(SimpleTestCase):
    def test_retrieve_returns_top_four_above_threshold(self):
        index = {
            "chunks": [
                chunk("L1-B01", [1.0, 0.0]),
                chunk("L1-B02", [0.9, 0.1]),
                chunk("L1-B03", [0.8, 0.2]),
                chunk("L1-B04", [0.7, 0.3]),
                chunk("L1-B05", [0.6, 0.4]),
                chunk("L1-B06", [-1.0, 0.0]),
            ]
        }
        with patch("apps.feedback.retrieval.similarity.load_index", return_value=index):
            matches = retrieve([1.0, 0.0])
        self.assertEqual(
            [match["chunk_id"] for match in matches],
            ["L1-B01", "L1-B02", "L1-B03", "L1-B04"],
        )

    def test_retrieve_tie_breaks_by_chunk_id_ascending(self):
        index = {
            "chunks": [
                chunk("L2-B02", [1.0, 0.0]),
                chunk("L1-B02", [1.0, 0.0]),
                chunk("L1-B01", [1.0, 0.0]),
            ]
        }
        with patch("apps.feedback.retrieval.similarity.load_index", return_value=index):
            matches = retrieve([1.0, 0.0])
        self.assertEqual(
            [match["chunk_id"] for match in matches],
            ["L1-B01", "L1-B02", "L2-B02"],
        )

    def test_retrieve_returns_empty_when_nothing_passes_threshold(self):
        index = {"chunks": [chunk("L1-B01", [1.0, 0.0])]}
        with patch("apps.feedback.retrieval.similarity.load_index", return_value=index):
            self.assertEqual(retrieve([0.0, 1.0]), [])

    def test_retrieve_is_deterministic_across_identical_calls(self):
        index = {
            "chunks": [
                chunk("L1-B02", [0.8, 0.2]),
                chunk("L1-B01", [1.0, 0.0]),
            ]
        }
        with patch("apps.feedback.retrieval.similarity.load_index", return_value=index):
            first = retrieve([1.0, 0.0])
            second = retrieve([1.0, 0.0])
        self.assertEqual(first, second)

    def test_cosine_similarity_matches_hand_computed_value(self):
        self.assertAlmostEqual(cosine_similarity([1.0, 2.0], [2.0, 1.0]), 0.8)
