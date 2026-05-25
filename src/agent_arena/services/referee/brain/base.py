"""RefereeBrain contract, context/decision dataclasses, and aggregate helper (S6)."""
from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum, auto
from typing import Any

logger = logging.getLogger(__name__)

_CRITERIA: tuple[str, ...] = ("logic", "evidence", "rebuttal", "persuasion")


class RequestKind(StrEnum):
    """The two consultation moments — no pre-turn call ever (6.a)."""

    EVALUATE_TURN = auto()
    RENDER_VERDICT = auto()


@dataclass
class RefereeContext:
    """Input to RefereeBrain.decide(); never serialized to the wire (6.b).

    score_trajectory is loop-private; carrying it here is safe (5.4e applies
    only to wire payloads).
    """

    request_kind: RequestKind
    state: dict[str, Any]
    move: dict[str, Any] | None
    rubric: dict[str, Any]
    judge_variant: str
    evidence_pack: dict[str, Any]
    score_trajectory: list[dict[str, Any]]


@dataclass
class RefereeDecision:
    """Output of RefereeBrain.decide(); kind-shaped (6.c, FR-RB4).

    EVALUATE_TURN: legal/flag/tell/turn_scores populated; verdict=None.
    RENDER_VERDICT: verdict populated; legal=True; others optional.
    """

    legal: bool = True
    flag: str | None = None
    tell: str | None = None
    turn_scores: dict[str, Any] | None = None
    verdict: dict[str, Any] | None = None


class RefereeBrain(ABC):
    """Stateless pure-function referee cognition contract (FR-RB1, 6.0).

    Two-kind dispatch via context.request_kind:
      EVALUATE_TURN  — after a Tier-1-passing move; returns legal/flag/tell/turn_scores.
      RENDER_VERDICT — once at terminal; returns the complete 2e verdict.

    The brain holds NO mutable match state and makes NO external calls.
    The loop owns the running numeric trajectory and injects it on every call.
    No LLM-only fields (prompt/token/temperature) appear here (6.i, FR-RB7).
    """

    @abstractmethod
    def decide(self, context: RefereeContext) -> RefereeDecision:
        """Pure function: same context in ⇒ same decision out."""


def aggregate_verdict(
    trajectory: list[dict[str, Any]],
    weights: dict[str, float],
    tiebreak_fn: Callable[[list[dict[str, Any]]], str],
) -> dict[str, Any]:
    """Deterministic aggregate of the per-turn trajectory → 2e verdict shape (6.h, REF-007).

    Per-criterion final = mean of that side's per-turn scores → weighted total.
    Total over any trajectory (all-zero / partial); never raises (FR-SB6, 9.f).
    """
    by_side: dict[str, dict[str, list[float]]] = {
        "PRO": {c: [] for c in _CRITERIA},
        "CON": {c: [] for c in _CRITERIA},
    }
    for item in trajectory:
        side = item.get("side", "PRO")
        ts = item.get("turn_scores") or {}
        for c in _CRITERIA:
            by_side.setdefault(side, {c: [] for c in _CRITERIA})
            by_side[side].setdefault(c, []).append(float(ts.get(c, 0.0)))

    mean_scores: dict[str, dict[str, float]] = {}
    for side in ("PRO", "CON"):
        mean_scores[side] = {
            c: (sum(vals) / len(vals) if vals else 0.0)
            for c, vals in by_side[side].items()
        }

    total_w = sum(weights.get(c, 0.0) for c in _CRITERIA) or 1.0
    weighted_totals = {
        side: round(
            sum(mean_scores[side][c] * weights.get(c, 0.0) for c in _CRITERIA) / total_w, 4
        )
        for side in ("PRO", "CON")
    }

    margin = round(weighted_totals["PRO"] - weighted_totals["CON"], 4)
    if margin > 0:
        winner = "PRO"
    elif margin < 0:
        winner = "CON"
    else:
        winner = tiebreak_fn(trajectory)

    return {
        "winner": winner,
        "margin": margin,
        "scores": mean_scores,
        "weighted_totals": weighted_totals,
        "rationale": f"Aggregate verdict: {winner} wins with margin {abs(margin):.2f}.",
    }
