import json
from datetime import datetime, timezone
from pathlib import Path

from apps.feedback.providers.openai_embeddings import (
    EMBEDDING_DIM,
    EMBEDDING_MODEL,
)
from apps.feedback.retrieval.chunking import (
    CHUNKING_POLICY,
    MAX_TOKENS,
    OVERLAP_TOKENS,
    TARGET_TOKENS,
    chunk_lessons,
    load_lesson_documents,
    source_fingerprint,
)


POLICY_VERSION = "RAG-RETRIEVAL-V1"


def build_index(*, source_dir, output_path, embedder, built_at=None):
    documents = load_lesson_documents(source_dir)
    if not documents:
        raise ValueError("No lesson source documents were found.")

    chunks = chunk_lessons(documents)
    token_usage = {}
    for chunk in chunks:
        embedding, token_count = embedder.embed(chunk["text"])
        chunk["embedding"] = embedding
        token_usage[chunk["chunk_id"]] = token_count

    source_fingerprints = {
        document["lesson_code"]: source_fingerprint(document["content"])
        for document in documents
    }
    index = {
        "_meta": {
            "policy_version": POLICY_VERSION,
            "chunking": CHUNKING_POLICY,
            "target_tokens": TARGET_TOKENS,
            "max_tokens": MAX_TOKENS,
            "overlap_tokens": OVERLAP_TOKENS,
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dim": EMBEDDING_DIM,
            "built_at": built_at or datetime.now(timezone.utc).isoformat(),
            "source_fingerprints": source_fingerprints,
            "token_usage": token_usage,
            "total_tokens": sum(token_usage.values()),
        },
        "chunks": chunks,
    }

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = output_path.with_suffix(output_path.suffix + ".tmp")
    temporary_path.write_text(
        json.dumps(index, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary_path.replace(output_path)
    return index
