import json
import os
import time
import urllib.error
import urllib.request

from apps.feedback.retrieval.chunking import approximate_token_count


EMBEDDING_MODEL = "gemini-embedding-001"
EMBEDDING_DIM = 1536
ENDPOINT = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{EMBEDDING_MODEL}:embedContent"
)
TASK_TYPES = {"document": "RETRIEVAL_DOCUMENT", "query": "RETRIEVAL_QUERY"}
MAX_ATTEMPTS = 3
TIMEOUT_SECONDS = 10.0


class EmbeddingConfigurationError(RuntimeError):
    pass


class EmbeddingResponseError(RuntimeError):
    pass


class GeminiRateLimitError(RuntimeError):
    pass


def _post_json(url, payload, headers, timeout):
    request = urllib.request.Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json", **headers},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code == 429:
            raise GeminiRateLimitError("Gemini embeddings rate limit reached.") from exc
        raise


class GeminiEmbeddingClient:
    """Google Gemini embeddings over the REST API (standard library only).

    Gemini embeds documents and queries differently, so the client is made for one
    purpose: "document" when building the index, "query" for a session's search.
    The API reports no token usage, so the count is the chunker's approximation.
    """

    model = EMBEDDING_MODEL

    def __init__(self, *, api_key=None, purpose="document", post=_post_json, sleep=time.sleep):
        api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise EmbeddingConfigurationError(
                "GEMINI_API_KEY is required to create embeddings."
            )
        if purpose not in TASK_TYPES:
            raise EmbeddingConfigurationError(f"Unknown embedding purpose: {purpose!r}.")
        self.api_key = api_key
        self.task_type = TASK_TYPES[purpose]
        self.post = post
        self.sleep = sleep

    def embed(self, text):
        payload = {
            "model": f"models/{EMBEDDING_MODEL}",
            "content": {"parts": [{"text": text}]},
            "taskType": self.task_type,
            "outputDimensionality": EMBEDDING_DIM,
        }
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                data = self.post(
                    ENDPOINT, payload, {"x-goog-api-key": self.api_key}, TIMEOUT_SECONDS
                )
                values = data.get("embedding", {}).get("values")
                if (
                    not isinstance(values, list)
                    or len(values) != EMBEDDING_DIM
                    or any(not isinstance(value, (int, float)) for value in values)
                ):
                    raise EmbeddingResponseError(
                        f"{EMBEDDING_MODEL} returned an invalid embedding."
                    )
                return [float(value) for value in values], approximate_token_count(text)
            except GeminiRateLimitError:
                if attempt == MAX_ATTEMPTS:
                    raise
                self.sleep(2 ** (attempt - 1))
