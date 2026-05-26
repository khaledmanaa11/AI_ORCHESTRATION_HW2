import json
import os
import time
from typing import TypeVar

from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)

_RETRYABLE_STATUS = (429, 500, 503)


class LLMError(Exception):
    """Custom exception for LLM client failures."""
    pass


# Keep alias for backward compatibility or in case it's referenced
GeminiError = LLMError


class LLMClient:
    """Wrapper for LLM SDK (configured for Gemini via google-genai)."""

    def __init__(self):
        load_dotenv()
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")
        self._client = genai.Client(api_key=api_key)

    def generate_json(self, prompt: str, model_name: str, schema: type[T]) -> T:
        """Generates structured JSON matching a Pydantic schema."""
        max_retries = 3
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=0.0,
        )

        for attempt in range(max_retries):
            try:
                result = self._client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config,
                )

                if not result.text:
                    raise LLMError("Empty response text from model.")

                data = json.loads(result.text)
                return schema.model_validate(data)

            except genai_errors.APIError as e:
                if e.code in _RETRYABLE_STATUS and attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                    continue
                raise LLMError(f"Failed after {attempt + 1} attempts: {str(e)}") from e
            except json.JSONDecodeError as e:
                raise LLMError(f"Failed to parse JSON response: {str(e)}") from e
            except LLMError:
                raise
            except Exception as e:
                raise LLMError(f"Unexpected error during generation: {str(e)}") from e
        raise LLMError("Max retries exceeded")

    def generate_text(self, prompt: str, model_name: str) -> str:
        """Generates plain text response."""
        max_retries = 3
        config = types.GenerateContentConfig(temperature=0.0)

        for attempt in range(max_retries):
            try:
                result = self._client.models.generate_content(
                    model=model_name,
                    contents=prompt,
                    config=config,
                )
                if not result.text:
                    return ""
                return result.text
            except genai_errors.APIError as e:
                if e.code in _RETRYABLE_STATUS and attempt < max_retries - 1:
                    time.sleep(1 * (attempt + 1))
                    continue
                raise LLMError(f"Failed after {attempt + 1} attempts: {str(e)}") from e
            except LLMError:
                raise
            except Exception as e:
                raise LLMError(f"Unexpected error during generation: {str(e)}") from e
        raise LLMError("Max retries exceeded")
