import json
import logging
import os
import random
import re
import shutil
import subprocess
import time
from typing import TypeVar

from dotenv import load_dotenv
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

from agent_arena.shared.api_gatekeeper import APIGatekeeper, get_default_gatekeeper

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

_RETRYABLE_STATUS = (429, 500, 502, 503, 504)
_MAX_RETRIES = 10
_MAX_BACKOFF_SECONDS = 120.0
_RETRY_DELAY_RE = re.compile(r"retry in (\d+(?:\.\d+)?)s")


def _get_temperature() -> float:
    """Read sampling temperature from env at call time (diagnostic studies)."""
    try:
        return float(os.environ.get("LLM_TEMPERATURE", "0.0"))
    except ValueError:
        return 0.0

# Gemini CLI subprocess timeout (generous — OAuth-backed Code Assist can be slow)
_CLI_TIMEOUT_SECONDS = 120.0
# Strip ```json ... ``` or ``` ... ``` fences the CLI sometimes wraps JSON in.
_JSON_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*(.*?)\s*```\s*$", re.DOTALL)


class LLMError(Exception):
    """Custom exception for LLM client failures."""
    pass


# Keep alias for backward compatibility or in case it's referenced
GeminiError = LLMError


def _backoff_seconds(exc: Exception, attempt: int) -> float:
    """Honor the server's suggested retry-after; else exponential + jitter.

    Jitter (±25%) prevents two players that hit a 503 at the same instant from
    syncing their retry schedules and re-colliding on every wake-up.
    """
    match = _RETRY_DELAY_RE.search(str(exc))
    base = float(match.group(1)) + 1.0 if match else 2.0 ** attempt
    jitter = base * random.uniform(-0.25, 0.25)
    return min(max(base + jitter, 1.0), _MAX_BACKOFF_SECONDS)


class GoogleGenAIClient:
    """API-key backend via google-genai SDK (AI Studio free tier)."""

    def __init__(self, gatekeeper: APIGatekeeper | None = None):
        load_dotenv()
        api_key = os.environ.get("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError("GOOGLE_API_KEY environment variable is not set")
        self._client = genai.Client(api_key=api_key)
        self._gatekeeper = gatekeeper or get_default_gatekeeper()

    def _generate(self, prompt: str, model_name: str, config: types.GenerateContentConfig):
        for attempt in range(_MAX_RETRIES):
            with self._gatekeeper.gate() as recorder:
                try:
                    result = self._client.models.generate_content(
                        model=model_name,
                        contents=prompt,
                        config=config,
                    )
                    recorder.record("success")
                    return result
                except genai_errors.APIError as e:
                    retryable = e.code in _RETRYABLE_STATUS
                    if retryable and attempt < _MAX_RETRIES - 1:
                        recorder.record("retryable_error")
                        backoff_exc = e
                        logger.warning(
                            "Gemini retryable error (attempt %d/%d, code=%s): %s",
                            attempt + 1, _MAX_RETRIES, e.code, str(e)[:200],
                        )
                    else:
                        recorder.record("fatal_error")
                        raise LLMError(f"Failed after {attempt + 1} attempts: {str(e)}") from e
            time.sleep(_backoff_seconds(backoff_exc, attempt))
        raise LLMError("Max retries exceeded")

    def generate_json(self, prompt: str, model_name: str, schema: type[T]) -> T:
        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=schema,
            temperature=_get_temperature(),
        )
        result = self._generate(prompt, model_name, config)
        if not result.text:
            raise LLMError("Empty response text from model.")
        try:
            data = json.loads(result.text)
        except json.JSONDecodeError as e:
            raise LLMError(f"Failed to parse JSON response: {str(e)}") from e
        return schema.model_validate(data)

    def generate_text(
        self,
        prompt: str,
        model_name: str,
        temperature: float | None = None,
        top_p: float | None = None,
        seed: int | None = None,
    ) -> str:
        config = types.GenerateContentConfig(
            temperature=temperature if temperature is not None else _get_temperature(),
            top_p=top_p,
            seed=seed,
        )
        result = self._generate(prompt, model_name, config)
        return result.text or ""


class GeminiCLIClient:
    """OAuth backend that shells out to the official `gemini` CLI.

    Uses the user's personal Google account via Gemini Code Assist for individuals
    (~60 RPM / 1000 RPD on Gemini 2.5 Pro). Requires `npm install -g @google/gemini-cli`
    and a one-time `gemini` login that caches OAuth creds under ~/.gemini/.
    """

    def __init__(self, gatekeeper: APIGatekeeper | None = None):
        binary = os.environ.get("GEMINI_CLI_BIN", "gemini")
        resolved = shutil.which(binary)
        if not resolved:
            raise LLMError(
                f"gemini CLI not found on PATH (looked for {binary!r}). "
                "Install with `npm install -g @google/gemini-cli` and run `gemini` once to log in."
            )
        self._binary = resolved
        self._gatekeeper = gatekeeper or get_default_gatekeeper()

    def _run(self, prompt: str, model_name: str) -> str:
        for attempt in range(_MAX_RETRIES):
            with self._gatekeeper.gate() as recorder:
                try:
                    proc = subprocess.run(
                        [self._binary, "-m", model_name, "-p", prompt],
                        capture_output=True,
                        text=True,
                        timeout=_CLI_TIMEOUT_SECONDS,
                        check=False,
                    )
                except subprocess.TimeoutExpired as e:
                    if attempt < _MAX_RETRIES - 1:
                        recorder.record("retryable_error")
                        backoff_exc = e
                    else:
                        recorder.record("fatal_error")
                        raise LLMError(f"gemini CLI timed out after {_CLI_TIMEOUT_SECONDS}s") from e
                else:
                    if proc.returncode == 0:
                        recorder.record("success")
                        return proc.stdout
                    stderr = proc.stderr or ""
                    retryable = any(
                        tok in stderr.lower() for tok in ("429", "rate", "quota", "unavailable", "retry")
                    )
                    if attempt < _MAX_RETRIES - 1 and retryable:
                        recorder.record("retryable_error")
                        backoff_exc = Exception(stderr)
                    else:
                        recorder.record("fatal_error")
                        raise LLMError(f"gemini CLI failed (exit {proc.returncode}): {stderr.strip()}")
            time.sleep(_backoff_seconds(backoff_exc, attempt))
        raise LLMError("Max retries exceeded")

    @staticmethod
    def _extract_json(raw: str) -> str:
        text = raw.strip()
        fence = _JSON_FENCE_RE.match(text)
        if fence:
            return fence.group(1).strip()
        # Fallback: locate first '{' .. last '}' to tolerate prose around the JSON.
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            return text[start : end + 1]
        return text

    def generate_json(self, prompt: str, model_name: str, schema: type[T]) -> T:
        schema_json = json.dumps(schema.model_json_schema())
        wrapped = (
            f"{prompt}\n\n"
            "Respond with ONLY a single JSON object — no prose, no markdown fences — "
            f"that strictly validates against this JSON Schema:\n{schema_json}"
        )
        raw = self._run(wrapped, model_name)
        body = self._extract_json(raw)
        try:
            data = json.loads(body)
        except json.JSONDecodeError as e:
            raise LLMError(f"Failed to parse JSON from gemini CLI: {str(e)}; raw={raw!r}") from e
        return schema.model_validate(data)

    def generate_text(
        self,
        prompt: str,
        model_name: str,
        temperature: float | None = None,  # noqa: ARG002 — CLI backend ignores sampling params
        top_p: float | None = None,  # noqa: ARG002
        seed: int | None = None,  # noqa: ARG002
    ) -> str:
        return self._run(prompt, model_name).strip()


class LLMClient:
    """Backend-selecting facade.

    `LLMClient(provider=...)` returns a `GoogleGenAIClient` or `GeminiCLIClient` instance based
    on the explicit `provider` argument, falling back to `LLM_PROVIDER` env var if not provided.
    Both backends expose the same `generate_json(prompt, model_name, schema)` and
    `generate_text(prompt, model_name)` interface, so this stays a drop-in for callsites and
    type annotations.
    """

    def __new__(cls, provider: str | None = None, gatekeeper: APIGatekeeper | None = None):
        load_dotenv()
        # Resolution order: explicit arg → env var (fallback) → raise error
        if provider is None:
            provider = os.environ.get("LLM_PROVIDER", "").strip().lower()
        else:
            provider = provider.strip().lower()

        if not provider:
            raise LLMError(
                "LLM provider not specified. Pass provider='google'|'gemini-cli' explicitly "
                "or set LLM_PROVIDER environment variable."
            )

        if provider in ("google", "google-genai", "ai-studio"):
            return GoogleGenAIClient(gatekeeper=gatekeeper)
        if provider in ("gemini-cli", "cli"):
            return GeminiCLIClient(gatekeeper=gatekeeper)
        raise LLMError(f"Unknown LLM provider: {provider!r}")
