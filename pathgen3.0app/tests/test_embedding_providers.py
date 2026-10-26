import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.feedback.providers import gemini_embeddings
from apps.feedback.providers.embeddings import (
    EMBEDDING_DIM,
    EmbeddingProviderError,
    embedding_model,
    embedding_provider,
    get_embedding_client,
)
from apps.feedback.providers.gemini_embeddings import (
    ENDPOINT,
    EmbeddingConfigurationError,
    EmbeddingResponseError,
    GeminiEmbeddingClient,
    GeminiRateLimitError,
)
from apps.feedback.retrieval.builder import build_index
from apps.feedback.retrieval.chunking import approximate_token_count


class RecordingPost:
    def __init__(self, *replies):
        self.replies = list(replies)
        self.calls = []

    def __call__(self, url, payload, headers, timeout):
        self.calls.append((url, payload, headers, timeout))
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def gemini_reply(size=EMBEDDING_DIM):
    return {"embedding": {"values": [0.5] * size}}


class GeminiEmbeddingClientTests(SimpleTestCase):
    def test_document_request_matches_the_gemini_api(self):
        post = RecordingPost(gemini_reply())
        client = GeminiEmbeddingClient(api_key="test-key", post=post)
        embedding, tokens = client.embed("Integers on a number line")

        url, payload, headers, timeout = post.calls[0]
        self.assertEqual(url, ENDPOINT)
        self.assertEqual(headers, {"x-goog-api-key": "test-key"})
        self.assertEqual(payload["model"], "models/gemini-embedding-001")
        self.assertEqual(payload["content"], {"parts": [{"text": "Integers on a number line"}]})
        self.assertEqual(payload["taskType"], "RETRIEVAL_DOCUMENT")
        self.assertEqual(payload["outputDimensionality"], EMBEDDING_DIM)
        self.assertEqual(timeout, gemini_embeddings.TIMEOUT_SECONDS)
        self.assertEqual(len(embedding), EMBEDDING_DIM)
        self.assertTrue(all(isinstance(value, float) for value in embedding))
        self.assertEqual(tokens, approximate_token_count("Integers on a number line"))

    def test_query_purpose_uses_the_query_task_type(self):
        post = RecordingPost(gemini_reply())
        GeminiEmbeddingClient(api_key="k", purpose="query", post=post).embed("Lesson: L1-1")
        self.assertEqual(post.calls[0][1]["taskType"], "RETRIEVAL_QUERY")

    def test_missing_key_is_refused(self):
        with patch.dict(os.environ, {"GEMINI_API_KEY": ""}):
            with self.assertRaises(EmbeddingConfigurationError):
                GeminiEmbeddingClient()

    def test_unknown_purpose_is_refused(self):
        with self.assertRaises(EmbeddingConfigurationError):
            GeminiEmbeddingClient(api_key="k", purpose="summary")

    def test_wrong_size_embedding_is_refused(self):
        client = GeminiEmbeddingClient(api_key="k", post=RecordingPost(gemini_reply(768)))
        with self.assertRaises(EmbeddingResponseError):
            client.embed("text")

    def test_rate_limit_retries_then_succeeds(self):
        sleeps = []
        post = RecordingPost(GeminiRateLimitError(), gemini_reply())
        client = GeminiEmbeddingClient(api_key="k", post=post, sleep=sleeps.append)
        embedding, _ = client.embed("text")
        self.assertEqual(len(embedding), EMBEDDING_DIM)
        self.assertEqual(sleeps, [1])

    def test_rate_limit_gives_up_after_the_last_attempt(self):
        post = RecordingPost(*[GeminiRateLimitError()] * gemini_embeddings.MAX_ATTEMPTS)
        client = GeminiEmbeddingClient(api_key="k", post=post, sleep=lambda _: None)
        with self.assertRaises(GeminiRateLimitError):
            client.embed("text")
        self.assertEqual(len(post.calls), gemini_embeddings.MAX_ATTEMPTS)


class EmbeddingProviderChoiceTests(SimpleTestCase):
    def test_default_provider_matches_the_committed_index(self):
        with patch.dict(os.environ, {"EMBEDDING_PROVIDER": ""}):
            self.assertEqual(embedding_provider(), "gemini")
            self.assertEqual(embedding_model(), "gemini-embedding-001")

    def test_openai_provider_can_still_be_chosen(self):
        with patch.dict(os.environ, {"EMBEDDING_PROVIDER": "openai"}):
            self.assertEqual(embedding_model(), "text-embedding-3-small")

    def test_gemini_provider_selects_the_gemini_client_and_model(self):
        with patch.dict(os.environ, {"EMBEDDING_PROVIDER": " Gemini ", "GEMINI_API_KEY": "k"}):
            self.assertEqual(embedding_model(), "gemini-embedding-001")
            client = get_embedding_client(purpose="query")
        self.assertIsInstance(client, GeminiEmbeddingClient)
        self.assertEqual(client.task_type, "RETRIEVAL_QUERY")

    def test_unknown_provider_is_refused(self):
        with patch.dict(os.environ, {"EMBEDDING_PROVIDER": "cohere"}):
            with self.assertRaises(EmbeddingProviderError):
                embedding_provider()

    def test_index_records_the_provider_model(self):
        class FakeEmbedder:
            def embed(self, text):
                return [0.1] * EMBEDDING_DIM, 3

        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            (root / "lessons").mkdir()
            lesson = {"code": "L1", "skill_codes": ["S1"], "content": {"source_text": "one two three"}}
            (root / "lessons" / "lesson_l1.json").write_text(
                json.dumps({"lesson": lesson}), encoding="utf-8"
            )
            with patch.dict(os.environ, {"EMBEDDING_PROVIDER": "gemini"}):
                index = build_index(
                    source_dir=root / "lessons",
                    output_path=root / "index.json",
                    embedder=FakeEmbedder(),
                )
        self.assertEqual(index["_meta"]["embedding_model"], "gemini-embedding-001")
        self.assertEqual(index["_meta"]["embedding_dim"], EMBEDDING_DIM)
