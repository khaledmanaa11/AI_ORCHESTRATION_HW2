"""Tests for DebateEngine and word_count helper (Module B)."""
from __future__ import annotations

from agent_arena.services.game.debate_engine import DebateEngine, word_count
from agent_arena.services.game.debate_state import DebateState

RULES = {
    "r": 3,
    "word_cap": 250,
    "retry_cap": 1,
    "first_speaker": "PRO",
    "motion": "AI is beneficial",
}


def make_engine(**overrides: object) -> DebateEngine:
    rules = {**RULES, **overrides}
    return DebateEngine(rules)


# ---------------------------------------------------------------------------
# word_count
# ---------------------------------------------------------------------------


def test_word_count_basic():
    assert word_count("hello world") == 2


def test_word_count_extra_spaces():
    assert word_count("  hello   world  ") == 2


def test_word_count_empty():
    assert word_count("") == 0


def test_word_count_single():
    assert word_count("word") == 1


# ---------------------------------------------------------------------------
# Initial state (FR-EN6)
# ---------------------------------------------------------------------------


def test_initial_state_shape():
    engine = make_engine()
    s = engine.get_initial_state()
    assert isinstance(s, DebateState)
    assert s.turn_number == 0
    assert s.status == "PENDING"
    assert s.transcript == ()
    assert s.motion == "AI is beneficial"


def test_initial_state_rules_snapshot():
    engine = make_engine()
    snap = engine.get_initial_state().rules_snapshot
    assert snap["R"] == 3
    assert snap["word_cap"] == 250
    assert snap["total_turns"] == 10


# ---------------------------------------------------------------------------
# Tier-1 validation (FR-EN4)
# ---------------------------------------------------------------------------


def test_validate_empty_text():
    engine = make_engine()
    s = engine.get_initial_state()
    ok, reason = engine.validate_move(s, {"text": ""})
    assert not ok
    assert reason == "empty"


def test_validate_whitespace_only():
    engine = make_engine()
    s = engine.get_initial_state()
    ok, reason = engine.validate_move(s, {"text": "   "})
    assert not ok
    assert reason == "empty"


def test_validate_over_length():
    engine = make_engine(word_cap=250)
    s = engine.get_initial_state()
    long_text = " ".join(["word"] * 251)
    ok, reason = engine.validate_move(s, {"text": long_text})
    assert not ok
    assert reason == "over_length"


def test_validate_exactly_at_cap_is_legal():
    engine = make_engine(word_cap=250)
    s = engine.get_initial_state()
    text = " ".join(["word"] * 250)
    ok, reason = engine.validate_move(s, {"text": text})
    assert ok
    assert reason is None


def test_validate_malformed_no_text_key():
    engine = make_engine()
    s = engine.get_initial_state()
    ok, reason = engine.validate_move(s, {})
    assert not ok
    assert reason == "malformed"


def test_validate_malformed_non_str_text():
    engine = make_engine()
    s = engine.get_initial_state()
    ok, reason = engine.validate_move(s, {"text": 5})
    assert not ok
    assert reason == "malformed"


def test_validate_malformed_not_dict():
    engine = make_engine()
    s = engine.get_initial_state()
    ok, reason = engine.validate_move(s, "raw string")
    assert not ok
    assert reason == "malformed"


def test_validate_legal_move():
    engine = make_engine()
    s = engine.get_initial_state()
    ok, reason = engine.validate_move(s, {"text": "This is a valid argument."})
    assert ok
    assert reason is None


# ---------------------------------------------------------------------------
# Legal-move descriptor (FR-EN5)
# ---------------------------------------------------------------------------


def test_get_legal_moves_length_one():
    engine = make_engine()
    s = engine.get_initial_state()
    moves = engine.get_legal_moves(s)
    assert len(moves) == 1


def test_get_legal_moves_opening_no_must_engage():
    engine = make_engine()
    s = engine.get_initial_state()
    descriptor = engine.get_legal_moves(s)[0]
    assert descriptor["phase"] == "OPENING"
    assert descriptor["must_engage"] is False
    assert descriptor["side"] == "PRO"


def test_get_legal_moves_rebuttal_must_engage():
    engine = make_engine()
    s = engine.get_initial_state()
    # advance to turn 2 (CON OPENING), then turn 3 is REBUTTAL
    s = engine.apply_move(s, {"text": "arg"}, tell="ok")
    s = engine.apply_move(s, {"text": "arg"}, tell="ok")
    descriptor = engine.get_legal_moves(s)[0]
    assert descriptor["phase"] == "REBUTTAL"
    assert descriptor["must_engage"] is True


# ---------------------------------------------------------------------------
# apply_move immutability (FR-EN1)
# ---------------------------------------------------------------------------


def test_apply_move_returns_new_state():
    engine = make_engine()
    s0 = engine.get_initial_state()
    s1 = engine.apply_move(s0, {"text": "Hello"})
    assert s0.turn_number == 0
    assert s1.turn_number == 1
    assert len(s1.transcript) == 1


def test_apply_move_does_not_mutate_input():
    engine = make_engine()
    s0 = engine.get_initial_state()
    original_id = id(s0.transcript)
    engine.apply_move(s0, {"text": "Hello"})
    assert id(s0.transcript) == original_id
    assert s0.turn_number == 0


# ---------------------------------------------------------------------------
# Penalized-empty turn (FR-EN3)
# ---------------------------------------------------------------------------


def test_penalized_empty_turn_advances_counter():
    engine = make_engine()
    s = engine.get_initial_state()
    s = engine.apply_move(s, {"text": ""}, flag="timeout", retry_count=1)
    assert s.turn_number == 1
    assert s.transcript[0].utterance == ""
    assert s.transcript[0].referee_flag == "timeout"


def test_penalized_timeout_flag_stored():
    engine = make_engine()
    s = engine.get_initial_state()
    s = engine.apply_move(s, {"text": ""}, flag="timeout")
    assert s.transcript[-1].referee_flag == "timeout"


def test_penalized_retry_exhausted_flag_stored():
    engine = make_engine()
    s = engine.get_initial_state()
    s = engine.apply_move(s, {"text": ""}, flag="retry_exhausted")
    assert s.transcript[-1].referee_flag == "retry_exhausted"


# ---------------------------------------------------------------------------
# Full 10-turn schedule + terminal detection (FR-EN2)
# ---------------------------------------------------------------------------


def test_full_schedule_reaches_terminal():
    engine = make_engine()
    s = engine.get_initial_state()
    for i in range(10):
        assert not engine.is_terminal(s), f"should not be terminal before turn {i + 1}"
        s = engine.apply_move(s, {"text": f"turn {i + 1} argument"}, tell="ack")
    assert engine.is_terminal(s)
    assert s.status == "COMPLETE"
    assert s.turn_number == 10


def test_not_terminal_before_last_turn():
    engine = make_engine()
    s = engine.get_initial_state()
    for _ in range(9):
        s = engine.apply_move(s, {"text": "argument"})
    assert not engine.is_terminal(s)


def test_status_in_progress_mid_match():
    engine = make_engine()
    s = engine.get_initial_state()
    s = engine.apply_move(s, {"text": "argument"})
    assert s.status == "IN_PROGRESS"
