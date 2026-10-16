import hashlib

from django.test import SimpleTestCase

from apps.feedback.retrieval.chunking import (
    MAX_TOKENS,
    OVERLAP_TOKENS,
    TARGET_TOKENS,
    approximate_token_count,
    canonical_content,
    chunk_lesson,
)


def lesson_document(*, word_count=900, lesson_code="L1"):
    words = [f"word{index:04d}" for index in range(word_count)]
    return {
        "lesson_code": lesson_code,
        "skill_codes": ["S1", "S5"],
        "content": {"source_text": " ".join(words)},
    }


class Phase10ChunkingTests(SimpleTestCase):
    def test_chunking_is_deterministic(self):
        document = lesson_document()
        self.assertEqual(chunk_lesson(document), chunk_lesson(document))

    def test_chunk_ids_are_stable_and_lexically_sortable(self):
        chunks = chunk_lesson(lesson_document(word_count=3000))
        chunk_ids = [chunk["chunk_id"] for chunk in chunks]
        self.assertEqual(chunk_ids, sorted(chunk_ids))
        self.assertEqual(chunk_ids[0], "L1-B01")
        self.assertEqual(chunk_ids[-1], f"L1-B{len(chunks):02d}")

    def test_no_chunk_exceeds_approximate_maximum(self):
        chunks = chunk_lesson(lesson_document())
        self.assertTrue(chunks)
        self.assertTrue(
            all(
                approximate_token_count(chunk["text"]) <= MAX_TOKENS
                for chunk in chunks
            )
        )

    def test_non_final_chunks_target_approximately_350_tokens(self):
        chunks = chunk_lesson(lesson_document())
        for chunk in chunks[:-1]:
            self.assertLessEqual(
                abs(approximate_token_count(chunk["text"]) - TARGET_TOKENS),
                1,
            )

    def test_adjacent_chunks_overlap_by_approximately_50_tokens(self):
        chunks = chunk_lesson(lesson_document())
        overlap_words = round(OVERLAP_TOKENS / 1.3)
        for left, right in zip(chunks, chunks[1:]):
            left_overlap = left["text"].split()[-overlap_words:]
            right_overlap = right["text"].split()[:overlap_words]
            self.assertEqual(left_overlap, right_overlap)
            self.assertLessEqual(
                abs(
                    approximate_token_count(" ".join(left_overlap))
                    - OVERLAP_TOKENS
                ),
                1,
            )

    def test_every_chunk_has_lesson_and_skill_codes(self):
        chunks = chunk_lesson(lesson_document())
        for chunk in chunks:
            self.assertEqual(chunk["lesson_code"], "L1")
            self.assertEqual(chunk["skill_codes"], ["S1", "S5"])

    def test_source_fingerprint_matches_canonical_lesson_content(self):
        document = lesson_document()
        expected = hashlib.sha256(
            canonical_content(document["content"])
        ).hexdigest()
        for chunk in chunk_lesson(document):
            self.assertEqual(chunk["source_fingerprint"], expected)
