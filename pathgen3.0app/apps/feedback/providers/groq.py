import os
import time

from groq import APIConnectionError, APITimeoutError, Groq


DEFAULT_MODEL = "gpt-oss-120b"
MAX_ATTEMPTS = 2
TIMEOUT_SECONDS = 20.0


class GroqConfigurationError(RuntimeError):
    pass


class GroqResponseError(RuntimeError):
    pass


class GroqFeedbackClient:
    def __init__(self, *, api_key=None, model=None, client=None, sleep=time.sleep):
        api_key = api_key or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise GroqConfigurationError(
                "GROQ_API_KEY is required to generate feedback."
            )
        self.model = model or os.getenv("GROQ_MODEL") or DEFAULT_MODEL
        self.client = client or Groq(
            api_key=api_key,
            timeout=TIMEOUT_SECONDS,
            max_retries=0,
        )
        self.sleep = sleep

    def generate(self, prompt):
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=0,
                    max_tokens=300,
                )
                content = response.choices[0].message.content
                if not isinstance(content, str):
                    raise GroqResponseError(
                        "Groq returned feedback in an invalid format."
                    )
                return content
            except (APIConnectionError, APITimeoutError):
                if attempt == MAX_ATTEMPTS:
                    raise
                self.sleep(1)
