"""Immutable game-state dataclasses for the debate specialisation (S5)."""
from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)

_SIDES: tuple[str, str] = ("PRO", "CON")


def total_turns(r: int) -> int:
    """Return the full schedule length: 2 + 2*r + 2."""
    return 2 + 2 * r + 2


def active_side(turn_number: int, first_speaker: str = "PRO") -> str:
    """Odd turns → first_speaker, even turns → the other side (5.4d, 1b)."""
    other = _SIDES[1] if first_speaker == _SIDES[0] else _SIDES[0]
    return first_speaker if turn_number % 2 == 1 else other


def phase(turn_number: int, r: int) -> str:
    """Map turn_number → OPENING / REBUTTAL / CLOSING for given r (5.4d)."""
    if turn_number <= 2:
        return "OPENING"
    if turn_number <= 2 + 2 * r:
        return "REBUTTAL"
    return "CLOSING"


def rebuttal_round(turn_number: int) -> int:
    """1-based rebuttal round: ⌈(t−2)/2⌉ (valid within REBUTTAL phase)."""
    return math.ceil((turn_number - 2) / 2)


@dataclass(frozen=True)
class TurnRecord:
    """Immutable public record of one executed turn (5.4b)."""

    turn_number: int
    side: str
    phase: str
    utterance: str
    word_count: int
    retry_count: int
    referee_tell: str | None
    referee_flag: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "turn_number": self.turn_number,
            "side": self.side,
            "phase": self.phase,
            "utterance": self.utterance,
            "word_count": self.word_count,
            "retry_count": self.retry_count,
            "referee_tell": self.referee_tell,
            "referee_flag": self.referee_flag,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TurnRecord:
        return cls(
            turn_number=data["turn_number"],
            side=data["side"],
            phase=data["phase"],
            utterance=data["utterance"],
            word_count=data["word_count"],
            retry_count=data["retry_count"],
            referee_tell=data.get("referee_tell"),
            referee_flag=data.get("referee_flag"),
        )


@dataclass(frozen=True)
class DebateMove:
    """A player's submitted utterance — exactly one public field (5.7a)."""

    text: str

    def to_dict(self) -> dict[str, str]:
        return {"text": self.text}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DebateMove:
        return cls(text=data["text"])


@dataclass(frozen=True)
class DebateState:
    """Immutable public game state for a debate match (5.4a, FR-ST2).

    rules_snapshot keys: R, word_cap, retry_cap, total_turns, first_speaker.
    phase / active_side are derived; they appear in to_dict() but are not stored.
    """

    motion: str
    turn_number: int = 0
    transcript: tuple[TurnRecord, ...] = ()
    status: str = "PENDING"
    verdict: dict | None = None
    rules_snapshot: dict = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a public-only dict; never includes private trajectory (5.4e)."""
        snap = self.rules_snapshot
        r = snap.get("R", 0)
        first = snap.get("first_speaker", "PRO")
        cur_phase = phase(self.turn_number, r) if self.turn_number > 0 else None
        cur_side = active_side(self.turn_number, first) if self.turn_number > 0 else None
        return {
            "motion": self.motion,
            "turn_number": self.turn_number,
            "phase": cur_phase,
            "active_side": cur_side,
            "transcript": [r.to_dict() for r in self.transcript],
            "status": self.status,
            "verdict": self.verdict,
            "rules_snapshot": dict(snap),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DebateState:
        """Lossless inverse of to_dict() (R-AC1)."""
        return cls(
            motion=data["motion"],
            turn_number=data["turn_number"],
            transcript=tuple(TurnRecord.from_dict(r) for r in data.get("transcript", [])),
            status=data.get("status", "PENDING"),
            verdict=data.get("verdict"),
            rules_snapshot=dict(data.get("rules_snapshot", {})),
        )
