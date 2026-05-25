"""Abstract base class for all game engines in agent-arena."""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any


class GameEngine(ABC):
    """Pure deterministic game mechanics; no LLM/network/disk."""

    @abstractmethod
    def get_initial_state(self) -> Any:
        """Return the initial game state before turn 1."""

    @abstractmethod
    def validate_move(self, _state: Any, move: Any) -> tuple[bool, str | None]:
        """Tier-1 mechanical validation.

        Returns (legal: bool, reason: str | None).
        reason is None when legal=True.
        """

    @abstractmethod
    def apply_move(self, state: Any, move: Any, **kwargs: Any) -> Any:
        """Return a new state with move applied; never mutates input."""

    @abstractmethod
    def get_legal_moves(self, state: Any) -> list[Any]:
        """Return the legal-move descriptor for the current state."""

    @abstractmethod
    def is_terminal(self, state: Any) -> bool:
        """Return True iff the game has reached a terminal state."""
