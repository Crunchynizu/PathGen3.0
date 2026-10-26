import json
from functools import lru_cache
from math import isfinite
from pathlib import Path

from django.conf import settings

from apps.feedback.providers.embeddings import EMBEDDING_DIM, embedding_model
from apps.feedback.retrieval.builder import POLICY_VERSION
from apps.feedback.retrieval.chunking import (
    CHUNKING_POLICY,
    load_lesson_documents,
    source_fingerprint,
)


INDEX_PATH = Path(settings.BASE_DIR) / "retrieval_index" / "pathgen_lessons.v1.json"
SOURCE_DIR = Path(settings.BASE_DIR) / "content_source" / "lessons"
REQUIRED_CHUNK_KEYS = {
    "chunk_id",
    "lesson_code",
    "skill_codes",
    "source_fingerprint",
    "text",
    "embedding",
}


class IndexStaleError(RuntimeError):
    pass


def _current_fingerprints():
    return {
        document["lesson_code"]: source_fingerprint(document["content"])
        for document in load_lesson_documents(SOURCE_DIR)
    }


def _validate_index(data):
    if not isinstance(data, dict):
        raise IndexStaleError("The retrieval index root must be an object.")
    meta = data.get("_meta")
    if not isinstance(meta, dict):
        raise IndexStaleError("The retrieval index metadata is missing.")
    if meta.get("policy_version") != POLICY_VERSION:
        raise IndexStaleError("The retrieval policy version is stale.")
    if meta.get("chunking") != CHUNKING_POLICY:
        raise IndexStaleError("The retrieval chunking policy is stale.")
    if meta.get("embedding_model") != embedding_model():
        raise IndexStaleError("The retrieval embedding model is stale.")
    if meta.get("embedding_dim") != EMBEDDING_DIM:
        raise IndexStaleError("The retrieval embedding dimension is invalid.")

    recorded = meta.get("source_fingerprints")
    if recorded != _current_fingerprints():
        raise IndexStaleError("The retrieval index source fingerprints are stale.")

    chunks = data.get("chunks")
    if not isinstance(chunks, list) or not chunks:
        raise IndexStaleError("The retrieval index has no chunks.")
    seen_ids = set()
    for chunk in chunks:
        if not isinstance(chunk, dict) or set(chunk) != REQUIRED_CHUNK_KEYS:
            raise IndexStaleError("A retrieval chunk has an invalid schema.")
        if not isinstance(chunk["chunk_id"], str) or chunk["chunk_id"] in seen_ids:
            raise IndexStaleError("Retrieval chunk IDs must be unique strings.")
        seen_ids.add(chunk["chunk_id"])
        embedding = chunk["embedding"]
        if (
            not isinstance(embedding, list)
            or len(embedding) != EMBEDDING_DIM
            or any(
                not isinstance(value, float) or not isfinite(value)
                for value in embedding
            )
        ):
            raise IndexStaleError("A retrieval chunk has an invalid embedding.")
        if chunk["source_fingerprint"] != recorded.get(chunk["lesson_code"]):
            raise IndexStaleError("A retrieval chunk fingerprint is inconsistent.")
    return data


@lru_cache(maxsize=1)
def load_index():
    try:
        data = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise IndexStaleError(f"The retrieval index is unavailable: {exc}") from exc
    return _validate_index(data)
