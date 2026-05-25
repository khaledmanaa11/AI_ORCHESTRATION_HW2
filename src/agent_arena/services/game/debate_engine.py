"""Pure deterministic debate mechanics; no LLM/network/disk (FR-EN7)."""
from __future__ import annotations

import logging
from typing import Any

from agent_arena.services.game.debate_state import (
    DebateMove,
    DebateState,
    TurnRecord,
    active_side,
    phase,
    total_turns,
)
from agent_arena.services.game.engine_base import GameEngine

logger = logging.getLogger(__name__)

_REASON_EMPTY = "empty"
_REASON_OVER_LENGTH = "over_length"
_REASON_MALFORMED = "malformed"


def word_count(text: str) -> int:
    """Single source of truth for word counting (whitespace split)."""
    return len(text.split())


class DebateEngine(GameEngine):
    """Pure deterministic debate mechanics; no LLM/network/disk (FR-EN7).

    Args:
        rules: dict with keys r, word_cap, retry_cap, first_speaker, motion.
    """

    def __init__(self, rules: dict[str, Any]) -> None:
        self._r: int = rules["r"]
        self._word_cap: int = rules["word_cap"]
        self._retry_cap: int = rules["retry_cap"]
        self._first_speaker: str = rules.get("first_speaker", "PRO")
        self._motion: str = rules["motion"]
        self._total: int = total_turns(self._r)

    def get_initial_state(self) -> DebateState:
        """Return turn_number=0, status=PENDING, empty transcript (FR-EN6)."""
        snap = {
            "R": self._r,
            "word_cap": self._word_cap,
            "retry_cap": self._retry_cap,
            "total_turns": self._total,
            "first_speaker": self._first_speaker,
        }
        return DebateState(motion=self._motion, rules_snapshot=snap)

    def validate_move(self, _state: DebateState, move: Any) -> tuple[bool, str | None]:
        """Tier-1 mechanical validation (FR-EN4).

        Returns (legal, reason_token | None).
        """
        if not isinstance(move, dict) or not isinstance(move.get("text"), str):
            return False, _REASON_MALFORMED
        text: str = move["text"]
        if not text or not text.strip():
            return False, _REASON_EMPTY
        if word_count(text) > self._word_cap:
            return False, _REASON_OVER_LENGTH
        return True, None

    def get_legal_moves(self, state: DebateState) -> list[Any]:
        """One-element constraint descriptor (FR-EN5, 5.7b)."""
        t = state.turn_number + 1
        snap = state.rules_snapshot
        cur_phase = phase(t, self._r)
        side = active_side(t, self._first_speaker)
        must_engage = cur_phase in ("REBUTTAL", "CLOSING")
        attempt = len(state.transcript) - state.turn_number  # retries so far
        return [
            {
                "type": "utterance",
                "turn_number": t,
                "side": side,
                "phase": cur_phase,
                "word_cap": snap.get("word_cap", self._word_cap),
                "must_engage": must_engage,
                "attempt": max(0, attempt),
                "max_attempts": snap.get("retry_cap", self._retry_cap),
            }
        ]

    def apply_move(
        self,
        state: DebateState,
        move: Any,
        *,
        tell: str | None = None,
        flag: str | None = None,
        retry_count: int = 0,
    ) -> DebateState:
        """Return fresh frozen DebateState with move appended (FR-EN1).

        Supports penalized-empty turns (utterance='', flag in {timeout,retry_exhausted})
        that still advance the turn counter (FR-EN3).
        """
        t = state.turn_number + 1
        if isinstance(move, DebateMove):
            text = move.text
        elif isinstance(move, dict):
            text = move.get("text", "")
        else:
            text = ""
        wc = word_count(text) if text else 0
        cur_phase = phase(t, self._r)
        side = active_side(t, self._first_speaker)
        record = TurnRecord(
            turn_number=t,
            side=side,
            phase=cur_phase,
            utterance=text,
            word_count=wc,
            retry_count=retry_count,
            referee_tell=tell,
            referee_flag=flag,
        )
        new_transcript = state.transcript + (record,)
        new_turn = t
        new_status = "COMPLETE" if new_turn == self._total else "IN_PROGRESS"
        return DebateState(
            motion=state.motion,
            turn_number=new_turn,
            transcript=new_transcript,
            status=new_status,
            verdict=state.verdict,
            rules_snapshot=state.rules_snapshot,
        )

    def is_terminal(self, state: DebateState) -> bool:
        """True iff turn_number == total_turns and all turns recorded (FR-EN2)."""
        return state.turn_number == self._total and len(state.transcript) == self._total
