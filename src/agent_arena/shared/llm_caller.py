from __future__ import annotations

from pydantic import BaseModel


class LLMCallerMixin:
    """Mixin for testability. Overridden in unit tests to mock LLM calls."""

    def _generate_json(self, prompt: str, schema: type[BaseModel]) -> BaseModel:
        return self._client.generate_json(prompt, self._model_name, schema)  # type: ignore
