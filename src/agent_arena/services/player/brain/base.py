"""PlayerBrain contract and context/decision dataclasses (FR-PB)."""
from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PlayerContext:
    """Input to PlayerBrain.generate() (FR-PB2)."""

    state: dict[str, Any]
    legal_moves: list[Any]
    rubric: dict[str, Any]
    evidence_pack: dict[str, Any]
    side: str
    ablation: dict[str, Any]
    scratchpad: list[Any]
    seed: int


@dataclass
class PlayerDecision:
    """Output of PlayerBrain.generate() (FR-PB3)."""

    move: dict[str, Any]
    trace: dict[str, Any] = field(default_factory=dict)


class PlayerBrain(ABC):
    """Stateless pure-function player brain contract (FR-PB1)."""

    @abstractmethod
    def generate(self, context: PlayerContext) -> PlayerDecision:
        """Generate a move and private trace from player context."""
