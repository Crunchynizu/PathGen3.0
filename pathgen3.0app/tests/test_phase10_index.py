import copy
import hashlib
import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import SimpleTestCase

from apps.feedback.providers.openai_embeddings import EMBEDDING_DIM
from apps.feedback.retrieval.builder import build_index
from apps.feedback.retrieval.chunking import approximate_token_count
from apps.feedback.retrieval.index import IndexStaleError, load_index


class FakeEmbeddingClient:
    def __init__(self, *args, **kwargs):
        self.calls = []

    def embed(self, text):
        self.calls.append(text)
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        value = int.from_bytes(digest[:4], "big") / (2**32)
        return [float(value)] * EMBEDDING_DIM, approximate_token_count(text)


def write_lesson(source_dir, *, text="one two three", lesson_code="L1"):
    content = {"source_text": text}
    payload = {
        "lesson": {
            "code": lesson_code,
            "skill_codes": ["S1"],
            "content": content,
        }
    }
    path = source_dir / f"lesson_{lesson_code.lower()}.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


class Phase10IndexTests(SimpleTestCase):
    def tearDown(self):
        load_index.cache_clear()
        super().tearDown()

    def _build(self, root, *, text="one two three"):
        source_dir = root / "lessons"
        source_dir.mkdir()
        write_lesson(source_dir, text=text)
        output_path = root / "pathgen_lessons.v1.json"
        index = build_index(
            source_dir=source_dir,
            output_path=output_path,
            embedder=FakeEmbeddingClient(),
            built_at="2026-01-01T00:00:00+00:00",
        )
        return source_dir, output_path, index

    def test_build_command_writes_a_valid_index_file(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_dir = root / "lessons"
            source_dir.mkdir()
            write_lesson(source_dir)
            output_path = root / "pathgen_lessons.v1.json"
            stdout = StringIO()
            with patch(
                "apps.feedback.management.commands.build_retrieval_index."
                "OpenAIEmbeddingClient",
                FakeEmbeddingClient,
            ):
                call_command(
                    "build_retrieval_index",
                    source_dir=source_dir,
                    output=output_path,
                    stdout=stdout,
                )
            data = json.loads(output_path.read_text(encoding="utf-8"))
            self.assertEqual(data["_meta"]["policy_version"], "RAG-RETRIEVAL-V1")
            self.assertEqual(len(data["chunks"]), 1)
            self.assertEqual(len(data["chunks"][0]["embedding"]), EMBEDDING_DIM)
            self.assertIn("chunks=1", stdout.getvalue())

    def test_two_builds_have_identical_chunks_ignoring_built_at(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_dir = root / "lessons"
            source_dir.mkdir()
            write_lesson(source_dir, text="word " * 900)
            first = build_index(
                source_dir=source_dir,
                output_path=root / "first.json",
                embedder=FakeEmbeddingClient(),
                built_at="2026-01-01T00:00:00+00:00",
            )
            second = build_index(
                source_dir=source_dir,
                output_path=root / "second.json",
                embedder=FakeEmbeddingClient(),
                built_at="2026-01-02T00:00:00+00:00",
            )
            first_without_time = copy.deepcopy(first)
            second_without_time = copy.deepcopy(second)
            first_without_time["_meta"].pop("built_at")
            second_without_time["_meta"].pop("built_at")
            self.assertEqual(first_without_time, second_without_time)

    def test_loader_rejects_recorded_fingerprint_mismatch(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_dir, output_path, index = self._build(root)
            index["_meta"]["source_fingerprints"]["L1"] = "0" * 64
            output_path.write_text(json.dumps(index), encoding="utf-8")
            with patch("apps.feedback.retrieval.index.INDEX_PATH", output_path), patch(
                "apps.feedback.retrieval.index.SOURCE_DIR", source_dir
            ):
                with self.assertRaises(IndexStaleError):
                    load_index()

    def test_loader_rejects_wrong_policy_version(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_dir, output_path, index = self._build(root)
            index["_meta"]["policy_version"] = "RAG-RETRIEVAL-OLD"
            output_path.write_text(json.dumps(index), encoding="utf-8")
            with patch("apps.feedback.retrieval.index.INDEX_PATH", output_path), patch(
                "apps.feedback.retrieval.index.SOURCE_DIR", source_dir
            ):
                with self.assertRaises(IndexStaleError):
                    load_index()

    def test_loader_caches_after_first_load(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_dir, output_path, expected = self._build(root)
            with patch("apps.feedback.retrieval.index.INDEX_PATH", output_path), patch(
                "apps.feedback.retrieval.index.SOURCE_DIR", source_dir
            ):
                first = load_index()
                output_path.unlink()
                second = load_index()
            self.assertIs(first, second)
            self.assertEqual(first, expected)

    def test_loader_rejects_index_after_source_changes(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            source_dir, output_path, _ = self._build(root)
            write_lesson(source_dir, text="changed lesson source")
            with patch("apps.feedback.retrieval.index.INDEX_PATH", output_path), patch(
                "apps.feedback.retrieval.index.SOURCE_DIR", source_dir
            ):
                with self.assertRaises(IndexStaleError):
                    load_index()
