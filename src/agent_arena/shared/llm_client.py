import json
import os
import re
import time
from typing import TypeVar

from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_RETRYABLE_STATUS = (429, 500, 503)
_MAX_RETRIES = 6
_MAX_BACKOFF_SECONDS = 65.0
_RETRY_DELAY_RE = re.compile(r"retry in (\d+(?:\.\d+)?)s")


class LLMError(Exception):
    """Custom exception for LLM client failures."""
    pass


# Keep alias for backward compatibility or in case it's referenced
GeminiError = LLMError


def _backoff_seconds(exc: Exception, attempt: int) -> float:
    """Honor the server's suggested retry-after; else exponential fallback."""
    match = _RETRY_DELAY_RE.search(str(exc))
    if match:
        return min(float(match.group(1)) + 1.0, _MAX_BACKOFF_SECONDS)
    return min(2.0 ** attempt, _MAX_BACKOFF_SECONDS)


class LLMClient:
    """Wrapper for LLM SDK (configured for Gemini via google-genai)."""

    def __init__(self):
        load_dotenv()
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")
        self._client = genai.Client(api_key=api_key)

    def _generate(self, prompt: str, model_name: str, config: types.GenerateContentConfig):
        """Call the model with retry/backoff that honors server retry-after."""
        for attempt in range(_MAX_RETRIES):
            try:
                return self._client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config,
                )
            except genai_errors.APIError as e:
                if e.code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES - 1:
                    time.sleep(_backoff_seconds(e, attempt))
                    continue
                raise LLMError(f"Failed after {attempt + 1} attempts: {str(e)}") from e
        raise LLMError("Max retries exceeded")

    def generate_json(self, prompt: str, model_name: str, schema: type[T]) -> T:
        """Generates structured JSON matching a Pydantic schema."""
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.0,
        )
        result = self._generate(prompt, model_name, config)
        if not result.text:
            raise LLMError("Empty response text from model.")
        try:
            data = json.loads(result.text)
        except json.JSONDecodeError as e:
            raise LLMError(f"Failed to parse JSON response: {str(e)}") from e
        return schema.model_validate(data)

    def generate_text(self, prompt: str, model_name: str) -> str:
        """Generates plain text response."""
        config = types.GenerateContentConfig(temperature=0.0)
        result = self._generate(prompt, model_name, config)
        return result.text or ""
