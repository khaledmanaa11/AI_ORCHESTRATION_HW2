"""Unit tests for the player-brain contract (base.py) and SeededPlayerBrain (RP1.1-1.4)."""
from __future__ import annotations

import dataclasses

import pytest

from agent_arena.services.player.brain.base import PlayerBrain, PlayerContext, PlayerDecision
from agent_arena.services.player.brain.seeded_brain import SeededPlayerBrain


def test_player_brain_abc_cannot_be_instantiated() -> None:
    """Instantiating the bare ABC must raise TypeError (RP1.3)."""
    with pytest.raises(TypeError):
        PlayerBrain()  # type: ignore[abstract]


def test_player_context_is_frozen() -> None:
    """PlayerContext is frozen; mutating fields raises FrozenInstanceError (RP1.1)."""
    ctx = PlayerContext(
        state={"turn_number": 1},
        legal_moves=[],
        rubric={},
        evidence_pack={},
        side="PRO",
        ablation={},
        scratchpad=[],
        seed=42,
    )
    with pytest.raises(dataclasses.FrozenInstanceError):
        ctx.seed = 100  # type: ignore[misc]


def test_player_decision_move_has_one_field() -> None:
    """PlayerDecision.move has one field and trace defaults to empty dict (RP1.2)."""
    decision = PlayerDecision(move={"text": "hello"})
    assert decision.move == {"text": "hello"}
    assert decision.trace == {}


def test_seeded_player_brain_generate_conformance() -> None:
    """SeededPlayerBrain.generate returns deterministic moves and empty trace (RP1.4)."""
    brain = SeededPlayerBrain(seed=42, side="PRO")
    ctx1 = PlayerContext(
        state={"turn_number": 2},
        legal_moves=[],
        rubric={},
        evidence_pack={},
        side="PRO",
        ablation={},
        scratchpad=[],
        seed=42,
    )
    ctx2 = PlayerContext(
        state={"turn_number": 2},
        legal_moves=[],
        rubric={},
        evidence_pack={},
        side="PRO",
        ablation={},
        scratchpad=[],
        seed=42,
    )

    dec1 = brain.generate(ctx1)
    dec2 = brain.generate(ctx2)

    assert dec1.move == dec2.move
    assert "text" in dec1.move
    assert len(dec1.move) == 1
    assert dec1.trace == {}
