import json
import os
import time
from typing import TypeVar

import google.generativeai as genai
from google.api_core.exceptions import InternalServerError, ResourceExhausted, RetryError
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)


class LLMError(Exception):
    """Custom exception for LLM client failures."""
    pass


# Keep alias for backward compatibility or in case it's referenced
GeminiError = LLMError


class LLMClient:
    """Wrapper for LLM SDK (configured for Gemini)."""

    def __init__(self):
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")
        genai.configure(api_key=api_key)

    def generate_json(self, prompt: str, model_name: str, schema: type[T]) -> T:
        """Generates structured JSON matching a Pydantic schema."""
        max_retries = 3
        model = genai.GenerativeModel(model_name)

        for attempt in range(max_retries):
            try:
                result = model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        response_mime_type="application/json",
                        response_schema=schema,
                        temperature=0.0
                    )
                )

                if not result.text:
                    raise LLMError("Empty response text from model.")

                data = json.loads(result.text)
                return schema.model_validate(data)

            except (RetryError, InternalServerError, ResourceExhausted) as e:
                if attempt == max_retries - 1:
                    raise LLMError(f"Failed after {max_retries} attempts: {str(e)}") from e
                time.sleep(1 * (attempt + 1))
            except json.JSONDecodeError as e:
                raise LLMError(f"Failed to parse JSON response: {str(e)}") from e
            except Exception as e:
                if "429" in str(e) or "503" in str(e) or "500" in str(e):
                    if attempt == max_retries - 1:
                        raise LLMError(f"Failed after {max_retries} attempts: {str(e)}") from e
                    time.sleep(1 * (attempt + 1))
                else:
                    raise LLMError(f"Unexpected error during generation: {str(e)}") from e
        raise LLMError("Max retries exceeded")

    def generate_text(self, prompt: str, model_name: str) -> str:
        """Generates plain text response."""
        max_retries = 3
        model = genai.GenerativeModel(model_name)

        for attempt in range(max_retries):
            try:
                result = model.generate_content(
                    prompt,
                    generation_config=genai.GenerationConfig(
                        temperature=0.0
                    )
                )
                if not result.text:
                    return ""
                return result.text
            except (RetryError, InternalServerError, ResourceExhausted) as e:
                if attempt == max_retries - 1:
                    raise LLMError(f"Failed after {max_retries} attempts: {str(e)}") from e
                time.sleep(1 * (attempt + 1))
            except Exception as e:
                if "429" in str(e) or "503" in str(e) or "500" in str(e):
                    if attempt == max_retries - 1:
                        raise LLMError(f"Failed after {max_retries} attempts: {str(e)}") from e
                    time.sleep(1 * (attempt + 1))
                else:
                    raise LLMError(f"Unexpected error during generation: {str(e)}") from e
        raise LLMError("Max retries exceeded")
