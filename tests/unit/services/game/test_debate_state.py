"""Tests for DebateState, DebateMove, TurnRecord and schedule helpers (Module A)."""
from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from agent_arena.services.game.debate_state import (
    DebateMove,
    DebateState,
    TurnRecord,
    active_side,
    phase,
    rebuttal_round,
    total_turns,
)

FORBIDDEN_KEYS = {"scores", "trajectory", "rubric", "weights", "evidence_pack", "reasoning"}

SNAP_R3 = {
    "R": 3,
    "word_cap": 250,
    "retry_cap": 1,
    "total_turns": 10,
    "first_speaker": "PRO",
}

# ---------------------------------------------------------------------------
# Schedule helpers
# ---------------------------------------------------------------------------


def test_total_turns_r3():
    assert total_turns(3) == 10


def test_total_turns_r2():
    assert total_turns(2) == 8


def test_total_turns_r1():
    assert total_turns(1) == 6


def test_active_side_pro_first_all_turns():
    for t in (1, 3, 5, 7, 9):
        assert active_side(t, "PRO") == "PRO", f"turn {t} should be PRO"
    for t in (2, 4, 6, 8, 10):
        assert active_side(t, "PRO") == "CON", f"turn {t} should be CON"


def test_active_side_con_first_flipped():
    for t in (1, 3, 5, 7, 9):
        assert active_side(t, "CON") == "CON", f"turn {t} should be CON when CON-first"
    for t in (2, 4, 6, 8, 10):
        assert active_side(t, "CON") == "PRO", f"turn {t} should be PRO when CON-first"


def test_active_side_default_is_pro():
    assert active_side(1) == "PRO"
    assert active_side(2) == "CON"


def test_phase_r3_schedule():
    assert phase(1, 3) == "OPENING"
    assert phase(2, 3) == "OPENING"
    for t in range(3, 9):
        assert phase(t, 3) == "REBUTTAL", f"turn {t} should be REBUTTAL"
    assert phase(9, 3) == "CLOSING"
    assert phase(10, 3) == "CLOSING"


def test_phase_r2_schedule():
    assert phase(1, 2) == "OPENING"
    assert phase(2, 2) == "OPENING"
    for t in (3, 4, 5, 6):
        assert phase(t, 2) == "REBUTTAL", f"turn {t} should be REBUTTAL (R=2)"
    assert phase(7, 2) == "CLOSING"
    assert phase(8, 2) == "CLOSING"


def test_rebuttal_round_r3():
    assert rebuttal_round(3) == 1
    assert rebuttal_round(4) == 1
    assert rebuttal_round(5) == 2
    assert rebuttal_round(6) == 2
    assert rebuttal_round(7) == 3
    assert rebuttal_round(8) == 3


# ---------------------------------------------------------------------------
# TurnRecord
# ---------------------------------------------------------------------------


def _make_turn(**kwargs: object) -> TurnRecord:
    defaults: dict = {
        "turn_number": 1,
        "side": "PRO",
        "phase": "OPENING",
        "utterance": "Hello world",
        "word_count": 2,
        "retry_count": 0,
        "referee_tell": None,
        "referee_flag": None,
    }
    defaults.update(kwargs)
    return TurnRecord(**defaults)


def test_turn_record_round_trip_minimal():
    r = _make_turn()
    assert TurnRecord.from_dict(r.to_dict()) == r


def test_turn_record_round_trip_with_tell_and_flag():
    r = _make_turn(referee_tell="[T1 PRO/OPENING] acknowledged — 2 words.", referee_flag="timeout")
    assert TurnRecord.from_dict(r.to_dict()) == r


def test_turn_record_frozen():
    r = _make_turn()
    with pytest.raises(FrozenInstanceError):
        r.turn_number = 99  # type: ignore[misc]


def test_turn_record_frozen_utterance():
    r = _make_turn()
    with pytest.raises(FrozenInstanceError):
        r.utterance = "different"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DebateMove
# ---------------------------------------------------------------------------


def test_debate_move_to_dict_shape():
    assert DebateMove("x").to_dict() == {"text": "x"}


def test_debate_move_round_trip():
    m = DebateMove("Hello world")
    assert DebateMove.from_dict(m.to_dict()) == m


def test_debate_move_only_text_field():
    m = DebateMove("test")
    assert set(m.to_dict().keys()) == {"text"}


def test_debate_move_frozen():
    m = DebateMove("hi")
    with pytest.raises(FrozenInstanceError):
        m.text = "bye"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# DebateState helpers
# ---------------------------------------------------------------------------


def _pre_start() -> DebateState:
    return DebateState(motion="AI is beneficial", rules_snapshot=SNAP_R3)


def _mid_match() -> DebateState:
    t = TurnRecord(1, "PRO", "OPENING", "Hello world", 2, 0, "[T1 PRO/OPENING] ack", None)
    return DebateState(
        motion="AI is beneficial",
        turn_number=1,
        transcript=(t,),
        status="IN_PROGRESS",
        rules_snapshot=SNAP_R3,
    )


def _terminal() -> DebateState:
    t = TurnRecord(10, "CON", "CLOSING", "Goodbye", 1, 0, "[T10 CON/CLOSING] done", None)
    verdict = {
        "winner": "PRO",
        "margin": 2.5,
        "scores": {"PRO": {}, "CON": {}},
        "weighted_totals": {"PRO": 7.5, "CON": 5.0},
        "rationale": "PRO argued more effectively.",
    }
    return DebateState(
        motion="AI is beneficial",
        turn_number=10,
        transcript=(t,),
        status="COMPLETE",
        verdict=verdict,
        rules_snapshot=SNAP_R3,
    )


# ---------------------------------------------------------------------------
# DebateState round-trips (R-AC1)
# ---------------------------------------------------------------------------


def test_debate_state_round_trip_pre_start():
    s = _pre_start()
    assert DebateState.from_dict(s.to_dict()) == s


def test_debate_state_round_trip_mid_match():
    s = _mid_match()
    assert DebateState.from_dict(s.to_dict()) == s


def test_debate_state_round_trip_terminal():
    s = _terminal()
    assert DebateState.from_dict(s.to_dict()) == s


def test_debate_state_frozen():
    s = _pre_start()
    with pytest.raises(FrozenInstanceError):
        s.turn_number = 5  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Public-only invariant (R-AC2, FR-ST6, FR-ST8)
# ---------------------------------------------------------------------------


def test_no_forbidden_keys_in_to_dict():
    for state in (_pre_start(), _mid_match(), _terminal()):
        d = state.to_dict()
        for key in FORBIDDEN_KEYS:
            assert key not in d, f"private key '{key}' leaked into to_dict()"


def test_no_forbidden_attrs_on_instance():
    s = _pre_start()
    for key in FORBIDDEN_KEYS:
        assert not hasattr(s, key), f"private attribute '{key}' found on DebateState"


def test_pre_start_derived_fields_none():
    d = _pre_start().to_dict()
    assert d["phase"] is None
    assert d["active_side"] is None


def test_mid_match_derived_phase_and_side():
    d = _mid_match().to_dict()
    assert d["phase"] == "OPENING"
    assert d["active_side"] == "PRO"
