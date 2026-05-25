"""SimpleRefereeBrain — deterministic, no external calls (S9, FR-SB1–FR-SB7)."""
from __future__ import annotations

import logging
from typing import Any

from agent_arena.services.referee.brain.base import (
    RefereeBrain,
    RefereeContext,
    RefereeDecision,
    RequestKind,
    aggregate_verdict,
)

logger = logging.getLogger(__name__)

# Frozen token set; never expanded at runtime (FR-SB2, 9.b)
CONCESSION_TOKENS: frozenset[str] = frozenset({
    "i concede",
    "i give up",
    "you win",
    "i forfeit",
    "i surrender",
    "i admit defeat",
})

_DEFAULT_WEIGHTS: dict[str, float] = {
    "logic": 30.0,
    "evidence": 30.0,
    "rebuttal": 25.0,
    "persuasion": 15.0,
}


def _is_concession(text: str) -> bool:
    """Case-fold scan for concession tokens (FR-SB2, 9.b)."""
    folded = text.casefold()
    return any(token in folded for token in CONCESSION_TOKENS)


def _score(word_count: int, word_cap: int) -> float:
    """Word-count-normalized score identical across 4 criteria (FR-SB4, 9.d)."""
    if word_cap <= 0:
        return 0.0
    return round(min(word_count / word_cap, 1.0) * 10, 2)


def simple_tiebreak(trajectory: list[dict[str, Any]]) -> str:
    """Tiebreak: greater cumulative word_count; still tied → PRO (FR-SB5, 9.e)."""
    wc: dict[str, int] = {"PRO": 0, "CON": 0}
    for item in trajectory:
        side = item.get("side", "PRO")
        wc[side] = wc.get(side, 0) + int(item.get("word_count", 0))
    if wc.get("PRO", 0) >= wc.get("CON", 0):
        return "PRO"
    return "CON"


class SimpleRefereeBrain(RefereeBrain):
    """Scripted, stateless referee brain; no LLM/network/disk/clock/RNG (FR-SB1, 9.a).

    EVALUATE_TURN: concession-keyword Tier-2 scan + number-free tell + word-count scores.
    RENDER_VERDICT: deterministic aggregate via aggregate_verdict + fixed tiebreak.
    judge_variant and evidence_pack are accepted but ignored (FR-SB7, 9.g).
    """

    def decide(self, context: RefereeContext) -> RefereeDecision:
        if context.request_kind == RequestKind.EVALUATE_TURN:
            return self._evaluate_turn(context)
        return self._render_verdict(context)

    def _evaluate_turn(self, context: RefereeContext) -> RefereeDecision:
        move = context.move or {}
        text: str = move.get("text", "") if isinstance(move, dict) else ""
        state = context.state

        # Derive public turn metadata from state
        t = state.get("turn_number", 0)
        side = state.get("active_side", "?")
        cur_phase = state.get("phase", "?")
        snap = state.get("rules_snapshot", {})
        word_cap: int = int(snap.get("word_cap", 250))
        wc = len(text.split()) if text else 0

        # Tier-2 legality: concession scan only (FR-SB2, 9.b)
        if _is_concession(text):
            return RefereeDecision(legal=False, flag="concession", tell=None, turn_scores=None)

        # Number-free tell from public data only (FR-SB3, 9.c)
        tell = f"[T{t} {side}/{cur_phase}] acknowledged — {wc} words."

        # Identical scores across 4 criteria (FR-SB4, 9.d)
        s = _score(wc, word_cap)
        turn_scores = {"logic": s, "evidence": s, "rebuttal": s, "persuasion": s}

        return RefereeDecision(legal=True, flag=None, tell=tell, turn_scores=turn_scores)

    def _render_verdict(self, context: RefereeContext) -> RefereeDecision:
        """Aggregate trajectory → 2e verdict; never raises (FR-SB5/SB6, 9.e/9.f)."""
        rubric = context.rubric or {}
        weights: dict[str, float] = rubric.get("weights", _DEFAULT_WEIGHTS)
        verdict = aggregate_verdict(context.score_trajectory, weights, simple_tiebreak)

        # Template rationale (9.e)
        winner = verdict["winner"]
        margin = abs(verdict.get("margin", 0.0))
        verdict["rationale"] = (
            f"SimpleRefereeBrain verdict: {winner} wins "
            f"with weighted margin {margin:.2f} (word-count proxy scoring)."
        )
        return RefereeDecision(legal=True, verdict=verdict)
