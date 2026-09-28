import os
import time

from openai import OpenAI, RateLimitError


EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIM = 1536
MAX_ATTEMPTS = 3


class EmbeddingConfigurationError(RuntimeError):
    pass


class EmbeddingResponseError(RuntimeError):
    pass


class OpenAIEmbeddingClient:
    def __init__(self, *, api_key=None, client=None, sleep=time.sleep):
        api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise EmbeddingConfigurationError(
                "OPENAI_API_KEY is required to create embeddings."
            )
        self.client = client or OpenAI(api_key=api_key, max_retries=0)
        self.sleep = sleep

    def embed(self, text):
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self.client.embeddings.create(
                    model=EMBEDDING_MODEL,
                    input=text,
                    encoding_format="float",
                    dimensions=EMBEDDING_DIM,
                )
                embedding = list(response.data[0].embedding)
                if len(embedding) != EMBEDDING_DIM or any(
                    not isinstance(value, float) for value in embedding
                ):
                    raise EmbeddingResponseError(
                        f"{EMBEDDING_MODEL} returned an invalid embedding."
                    )
                usage = getattr(response, "usage", None)
                token_count = getattr(usage, "prompt_tokens", None)
                if not isinstance(token_count, int) or token_count < 0:
                    raise EmbeddingResponseError(
                        "The embeddings response did not include prompt token usage."
                    )
                return embedding, token_count
            except RateLimitError:
                if attempt == MAX_ATTEMPTS:
                    raise
                self.sleep(2 ** (attempt - 1))
