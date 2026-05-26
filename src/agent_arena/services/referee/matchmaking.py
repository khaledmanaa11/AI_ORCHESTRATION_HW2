"""Debate-specific match setup: game_config assembly + seeded side assignment (S7, T4.4)."""
from __future__ import annotations

import logging
import random
from dataclasses import dataclass
from typing import Any

from agent_arena.services.game.debate_state import DebateState, total_turns

logger = logging.getLogger(__name__)

_SIDES: tuple[str, str] = ("PRO", "CON")
_CRITERIA: tuple[str, ...] = ("logic", "evidence", "rebuttal", "persuasion")
_TIE_BREAK: str = "first_speaker"
_VERDICT_STRUCTURE: str = "2e"
_CONDUCT_GATE: dict[str, Any] = {"max_violations": 3, "penalty": "floor_score"}


class MatchAbortError(Exception):
    """Raised on pre-GAME_START failures (FR-FT6, 8.5). No results row is written."""


def build_game_config(
    motion: str,
    weights: dict[str, int],
    format_cfg: dict[str, Any],
    evidence_pack: dict[str, Any],
) -> dict[str, Any]:
    """Assemble the player-bound game_config dict (7.f/7.g).

    judge_variant is never included — it is referee-private (RF1.2, R-AC2).
    The identical dict is sent to both players (RF1.3 symmetry).
    """
    r = format_cfg.get("rebuttal_rounds", 3)
    return {
        "motion": motion,
        "rubric": {"criteria": list(_CRITERIA), "weights": dict(weights)},
        "tie_break": _TIE_BREAK,
        "verdict_structure": _VERDICT_STRUCTURE,
        "conduct_gate": dict(_CONDUCT_GATE),
        "format": {
            "total_turns": total_turns(r),
            "R": r,
            "word_cap": format_cfg.get("word_cap", 250),
            "first_speaker": format_cfg.get("first_speaker", "PRO"),
            "retry_cap": format_cfg.get("retry_cap", 1),
            "phase_schedule": {
                "opening_turns": 2,
                "rebuttal_rounds": r,
                "closing_turns": 2,
            },
        },
        "evidence_pack": evidence_pack,
    }


def assign_sides(player_ids: list[str], seed: int) -> dict[str, str]:
    """Return {player_id: side} with seeded PRO/CON assignment (1e, RF2.1).

    Same seed + same player_ids order → identical assignment every run (R-AC4).
    """
    if len(player_ids) != 2:
        raise ValueError(f"Exactly 2 players required; got {len(player_ids)}")
    rng = random.Random(seed)
    sides = list(_SIDES)
    rng.shuffle(sides)
    return dict(zip(player_ids, sides, strict=True))


def _build_rules_snapshot(format_cfg: dict[str, Any]) -> dict[str, Any]:
    r = format_cfg.get("rebuttal_rounds", 3)
    return {
        "R": r,
        "word_cap": format_cfg.get("word_cap", 250),
        "retry_cap": format_cfg.get("retry_cap", 1),
        "total_turns": total_turns(r),
        "first_speaker": format_cfg.get("first_speaker", "PRO"),
    }


@dataclass(frozen=True)
class MatchSetup:
    """Immutable result of a successful pre-game setup phase."""

    match_id: str
    side_map: dict[str, str]       # {player_id: "PRO"/"CON"}
    game_config: dict[str, Any]    # player-bound, never contains judge_variant
    judge_variant: str
    initial_state: DebateState
    first_speaker: str


def setup_match(
    match_id: str,
    player_ids: list[str],
    seed: int,
    motion: str,
    weights: dict[str, int],
    format_cfg: dict[str, Any],
    evidence_pack: dict[str, Any],
    judge_variant: str = "naive",
) -> MatchSetup:
    """Build the full pre-GAME_START package; raises MatchAbortError on bad input.

    On MatchAbortError the caller must NOT call write_trajectory (FR-FT6, 8.5).
    """
    if len(player_ids) != 2:
        raise MatchAbortError(f"Expected 2 players, got {len(player_ids)}")
    side_map = assign_sides(player_ids, seed)
    game_config = build_game_config(motion, weights, format_cfg, evidence_pack)
    rules = _build_rules_snapshot(format_cfg)
    initial_state = DebateState(
        motion=motion,
        turn_number=0,
        transcript=(),
        status="PENDING",
        verdict=None,
        rules_snapshot=rules,
    )
    return MatchSetup(
        match_id=match_id,
        side_map=side_map,
        game_config=game_config,
        judge_variant=judge_variant,
        initial_state=initial_state,
        first_speaker=format_cfg.get("first_speaker", "PRO"),
    )
