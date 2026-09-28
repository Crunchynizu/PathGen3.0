import hashlib
import json
from pathlib import Path

CHUNKING_POLICY = "lesson-blocks-v1"
TARGET_TOKENS = 350
MAX_TOKENS = 500
OVERLAP_TOKENS = 50

# Approximate token counter:
# - Deterministic.
# - Targets the 350/500/50 token policy approximately.
# - tiktoken is intentionally avoided to preserve the 8-package stack.
def approximate_token_count(text):
    return max(1, round(len(text.split()) * 1.3))


def _word_count_for_token_target(token_target):
    return max(1, round(token_target / 1.3))


def canonical_content(content):
    return json.dumps(
        content,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")


def source_fingerprint(content):
    return hashlib.sha256(canonical_content(content)).hexdigest()


def load_lesson_documents(source_dir):
    documents = []
    for path in sorted(Path(source_dir).glob("lesson_*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        lesson = data["lesson"]
        documents.append(
            {
                "lesson_code": lesson["code"],
                "skill_codes": list(lesson["skill_codes"]),
                "content": lesson["content"],
            }
        )
    return sorted(documents, key=lambda item: item["lesson_code"])


def _word_windows(words):
    if not words:
        return []
    if approximate_token_count(" ".join(words)) <= MAX_TOKENS:
        return [words]

    target_words = _word_count_for_token_target(TARGET_TOKENS)
    overlap_words = _word_count_for_token_target(OVERLAP_TOKENS)
    windows = []
    start = 0
    while start < len(words):
        end = min(start + target_words, len(words))
        window = words[start:end]
        windows.append(window)
        if end == len(words):
            break
        start = end - overlap_words
    return windows


def chunk_lesson(document):
    content = document["content"]
    text = content["source_text"]
    fingerprint = source_fingerprint(content)
    windows = _word_windows(text.split())
    return [
        {
            "chunk_id": f"{document['lesson_code']}-B{index:02d}",
            "lesson_code": document["lesson_code"],
            "skill_codes": list(document["skill_codes"]),
            "source_fingerprint": fingerprint,
            "text": " ".join(window),
        }
        for index, window in enumerate(windows, start=1)
    ]


def chunk_lessons(documents):
    chunks = []
    for document in sorted(documents, key=lambda item: item["lesson_code"]):
        chunks.extend(chunk_lesson(document))
    return chunks
