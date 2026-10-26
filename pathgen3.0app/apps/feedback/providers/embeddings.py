"""Chooses the embedding provider from EMBEDDING_PROVIDER ("openai" or "gemini").

The index records which model built it, and queries must use that same model, so the
provider is one setting read in one place. Both produce 1536-dimensional vectors.
The default matches the committed index (built with Gemini on 2026-10-26); after
changing the provider, rebuild the index with `manage.py build_retrieval_index`.
"""

import os

from apps.feedback.providers import gemini_embeddings, openai_embeddings


EMBEDDING_DIM = 1536
DEFAULT_PROVIDER = "gemini"


class EmbeddingProviderError(RuntimeError):
    pass


def embedding_provider():
    provider = (os.getenv("EMBEDDING_PROVIDER") or DEFAULT_PROVIDER).strip().lower()
    if provider not in ("openai", "gemini"):
        raise EmbeddingProviderError(
            f"EMBEDDING_PROVIDER must be 'openai' or 'gemini', not {provider!r}."
        )
    return provider


def embedding_model():
    if embedding_provider() == "gemini":
        return gemini_embeddings.EMBEDDING_MODEL
    return openai_embeddings.EMBEDDING_MODEL


def get_embedding_client(purpose="document"):
    """purpose: "document" for building the index, "query" for a session's search."""
    if embedding_provider() == "gemini":
        return gemini_embeddings.GeminiEmbeddingClient(purpose=purpose)
    return openai_embeddings.OpenAIEmbeddingClient()
