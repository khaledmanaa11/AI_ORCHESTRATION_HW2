"""Tests for DebateGameLoop, run_turn, and recv_timed (Module E)."""
from __future__ import annotations

import json
import queue
from datetime import datetime, timezone
from typing import Any

import pytest

from agent_arena.constants import PROTOCOL_VERSION, TERMINATED_ABORTED, TERMINATED_DISCONNECT
from agent_arena.services.game.debate_engine import DebateEngine
from agent_arena.services.game.debate_state import DebateState
from agent_arena.services.protocol.codec import encode
from agent_arena.services.protocol.envelope import Envelope
from agent_arena.services.protocol.message_types import MessageType
from agent_arena.services.referee._turn_runner import recv_timed
from agent_arena.services.referee.brain.simple_brain import SimpleRefereeBrain
from agent_arena.services.referee.game_loop import DebateGameLoop
from agent_arena.shared.transport.channel import ConnectionClosedError, InMemoryChannel

RULES = {"r": 3, "word_cap": 250, "retry_cap": 1,
         "first_speaker": "PRO", "motion": "AI is beneficial"}
RUBRIC = {"weights": {"logic": 30.0, "evidence": 30.0,
                      "rebuttal": 25.0, "persuasion": 15.0}}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_engine() -> DebateEngine:
    return DebateEngine(RULES)


def _make_loop(pro_ch: InMemoryChannel, con_ch: InMemoryChannel,
               timeout: float = 5.0) -> DebateGameLoop:
    return DebateGameLoop(
        match_id="test-match",
        engine=_make_engine(),
        brain=SimpleRefereeBrain(),
        channels={"PRO": pro_ch, "CON": con_ch},
        move_timeout_seconds=timeout,
        rubric=RUBRIC,
    )


def _make_move_envelope(text: str, seq: int = 1) -> bytes:
    return encode(Envelope(
        protocol_version=PROTOCOL_VERSION,
        type=MessageType.MOVE_SUBMIT,
        match_id="test-match",
        sender="player",
        seq=seq,
        timestamp=datetime.now(timezone.utc).isoformat(),
        payload={"move": {"text": text}},
    ))


def _drain_outbox(ch: InMemoryChannel) -> list[dict[str, Any]]:
    """Read all queued messages from a channel's output queue."""
    msgs: list[dict[str, Any]] = []
    q = ch._out_q  # type: ignore[attr-defined]
    while not q.empty():
        item = q.get_nowait()
        if item is None:
            break
        msgs.append(json.loads(item))
    return msgs


def _feed_moves(in_q: queue.Queue, texts: list[str]) -> None:
    """Pre-load moves into a player's input queue."""
    for i, text in enumerate(texts):
        in_q.put(_make_move_envelope(text, seq=i + 1))


# ---------------------------------------------------------------------------
# recv_timed
# ---------------------------------------------------------------------------

def test_recv_timed_returns_bytes():
    a, b = InMemoryChannel.make_pair()
    b.send(b"hello")
    result = recv_timed(a, timeout=1.0)
    assert result == b"hello"


def test_recv_timed_returns_none_on_timeout():
    a, _b = InMemoryChannel.make_pair()
    result = recv_timed(a, timeout=0.05)
    assert result is None


def test_recv_timed_raises_connection_closed():
    a, b = InMemoryChannel.make_pair()
    b.close()
    with pytest.raises(ConnectionClosedError):
        recv_timed(a, timeout=1.0)


# ---------------------------------------------------------------------------
# RE8.1 — Happy path: 10 turns → exactly one GAME_OVER
# ---------------------------------------------------------------------------

def test_happy_path_one_game_over():
    pro_a, pro_b = InMemoryChannel.make_pair()   # referee side, player side
    con_a, con_b = InMemoryChannel.make_pair()

    # Feed 10 utterances across PRO/CON
    utterance = "This is a solid argument for the motion."
    for i in range(10):
        side_q = pro_b._out_q if (i % 2 == 0) else con_b._out_q  # type: ignore[attr-defined]
        side_q.put(_make_move_envelope(utterance, seq=i + 1))

    loop = _make_loop(pro_a, con_a)
    final_state = loop.run()

    assert final_state.status == "COMPLETE"
    assert final_state.verdict is not None
    assert final_state.verdict["winner"] in ("PRO", "CON")

    # Exactly one GAME_OVER on each channel
    for ch in (pro_a, con_a):
        msgs = _drain_outbox(ch)
        game_overs = [m for m in msgs if m.get("type") == MessageType.GAME_OVER.value]
        assert len(game_overs) == 1, f"Expected 1 GAME_OVER, got {len(game_overs)}"


# ---------------------------------------------------------------------------
# RE8.2 — Retry gate: illegal → legal; exhaustion → penalised turn
# ---------------------------------------------------------------------------

def test_retry_gate_illegal_then_legal():
    pro_a, pro_b = InMemoryChannel.make_pair()
    con_a, con_b = InMemoryChannel.make_pair()

    # PRO turn 1: first submit is empty (Tier-1 reject), second is valid
    pro_b._out_q.put(_make_move_envelope(""))             # type: ignore[attr-defined]
    for i in range(1, 10):
        side_q = pro_b._out_q if (i % 2 == 0) else con_b._out_q  # type: ignore[attr-defined]
        side_q.put(_make_move_envelope("valid argument here", seq=i + 1))
    # put the valid retry for turn 1 back on pro
    pro_b._out_q.put(_make_move_envelope("valid argument here", seq=20))  # type: ignore[attr-defined]

    # Re-build with proper sequence: empty first, then 10 valids
    pro_a2, pro_b2 = InMemoryChannel.make_pair()
    con_a2, con_b2 = InMemoryChannel.make_pair()
    pro_b2._out_q.put(_make_move_envelope(""))                        # type: ignore[attr-defined]
    pro_b2._out_q.put(_make_move_envelope("solid argument on pro"))   # type: ignore[attr-defined]
    for i in range(9):
        q = con_b2._out_q if (i % 2 == 0) else pro_b2._out_q         # type: ignore[attr-defined]
        q.put(_make_move_envelope(f"turn {i + 2} argument"))

    loop2 = _make_loop(pro_a2, con_a2)
    state = loop2.run()
    assert state.status == "COMPLETE"
    # PRO turn 1 should have retry_count > 0
    assert state.transcript[0].retry_count == 1


def test_retry_exhaustion_produces_penalised_turn():
    """Both attempts fail → penalised empty turn, match continues to completion."""
    pro_a, pro_b = InMemoryChannel.make_pair()
    con_a, con_b = InMemoryChannel.make_pair()

    # PRO gets retry_cap=1, so 2 illegal moves → penalty
    pro_b._out_q.put(_make_move_envelope(""))   # type: ignore[attr-defined]
    pro_b._out_q.put(_make_move_envelope(""))   # type: ignore[attr-defined]
    # Fill remaining 9 turns
    for i in range(9):
        q = con_b._out_q if (i % 2 == 0) else pro_b._out_q  # type: ignore[attr-defined]
        q.put(_make_move_envelope("argument text here"))

    loop = _make_loop(pro_a, con_a)
    state = loop.run()
    assert state.status == "COMPLETE"
    assert state.transcript[0].referee_flag == "retry_exhausted"
    assert state.transcript[0].utterance == ""


# ---------------------------------------------------------------------------
# RE8.3 — Move-timeout → penalised skip, no forfeit; shared budget
# ---------------------------------------------------------------------------

def test_timeout_produces_penalised_turn_not_forfeit():
    """Patch recv_timed to return None once (PRO turn 1), then real data for turns 2-10."""
    from unittest.mock import patch

    pro_a, pro_b = InMemoryChannel.make_pair()
    con_a, con_b = InMemoryChannel.make_pair()

    # Pre-load moves for turns 2-10 (CON: i=0,2,4,6,8; PRO: i=1,3,5,7)
    for i in range(9):
        q = con_b._out_q if (i % 2 == 0) else pro_b._out_q  # type: ignore[attr-defined]
        q.put(_make_move_envelope("argument text"))

    real_recv = recv_timed
    first_call = [True]

    def patched_recv(ch, timeout):
        if first_call[0]:                # First call = PRO turn 1 → simulate timeout
            first_call[0] = False
            return None
        return real_recv(ch, timeout)    # All subsequent calls use real recv

    with patch("agent_arena.services.referee._turn_runner.recv_timed", patched_recv):
        loop = _make_loop(pro_a, con_a, timeout=2.0)
        state = loop.run()

    assert state.status == "COMPLETE"
    assert state.transcript[0].referee_flag == "timeout"
    assert state.transcript[0].utterance == ""
    assert state.transcript[0].word_count == 0


# ---------------------------------------------------------------------------
# RE8.4 — Disconnect → forced tagged verdict; malformed content → drop frame
# ---------------------------------------------------------------------------

def test_disconnect_produces_tagged_game_over():
    pro_a, pro_b = InMemoryChannel.make_pair()
    con_a, con_b = InMemoryChannel.make_pair()

    # PRO turn 1 closes the connection
    pro_b.close()

    loop = _make_loop(pro_a, con_a, timeout=1.0)
    state = loop.run()
    assert state.status == "COMPLETE"
    assert state.verdict is not None
    assert state.verdict.get("terminated_reason") == TERMINATED_DISCONNECT

    # Exactly one GAME_OVER despite disconnect
    msgs = _drain_outbox(pro_a) + _drain_outbox(con_a)
    game_overs = [m for m in msgs if m.get("type") == MessageType.GAME_OVER.value]
    assert len(game_overs) == 2   # one per channel


def test_malformed_content_sends_error_and_continues():
    """Malformed bytes → MALFORMED_MESSAGE ERROR; turn clock still ticking."""
    pro_a, pro_b = InMemoryChannel.make_pair()
    con_a, con_b = InMemoryChannel.make_pair()

    # PRO turn 1: garbage frame then valid move
    pro_b._out_q.put(b"not valid json at all")   # type: ignore[attr-defined]
    pro_b._out_q.put(_make_move_envelope("real argument here"))  # type: ignore[attr-defined]
    for i in range(9):
        q = con_b._out_q if (i % 2 == 0) else pro_b._out_q  # type: ignore[attr-defined]
        q.put(_make_move_envelope("argument"))

    loop = _make_loop(pro_a, con_a, timeout=2.0)
    state = loop.run()
    assert state.status == "COMPLETE"

    # Should have sent MALFORMED error to PRO
    msgs = _drain_outbox(pro_a)
    error_msgs = [m for m in msgs
                  if m.get("type") == MessageType.ERROR.value
                  and m.get("payload", {}).get("code") == "MALFORMED_MESSAGE"]
    assert len(error_msgs) >= 1


# ---------------------------------------------------------------------------
# RE8.5 — Injected exception → try/finally still yields one GAME_OVER (8.6)
# ---------------------------------------------------------------------------

def test_injected_exception_still_yields_game_over():
    pro_a, pro_b = InMemoryChannel.make_pair()
    con_a, con_b = InMemoryChannel.make_pair()

    for i in range(10):
        q = pro_b._out_q if (i % 2 == 0) else con_b._out_q  # type: ignore[attr-defined]
        q.put(_make_move_envelope("argument"))

    loop = _make_loop(pro_a, con_a, timeout=2.0)

    # Patch _run_turns to raise immediately
    def _boom(_state: DebateState) -> DebateState:
        raise RuntimeError("injected test exception")

    loop._run_turns = _boom  # type: ignore[method-assign]
    state = loop.run()

    # Must still reach GAME_OVER
    assert state.status == "COMPLETE"
    assert state.verdict is not None
    assert state.verdict.get("terminated_reason") == TERMINATED_ABORTED

    msgs = _drain_outbox(pro_a) + _drain_outbox(con_a)
    game_overs = [m for m in msgs if m.get("type") == MessageType.GAME_OVER.value]
    assert len(game_overs) == 2


# ---------------------------------------------------------------------------
# RE8.6 — Brain-call count: no pre-turn call (FR-RB2, 6.a)
# ---------------------------------------------------------------------------

def test_brain_call_count_no_preturn_call():
    """brain.decide calls == number of scored turns + 1 (RENDER_VERDICT)."""
    pro_a, pro_b = InMemoryChannel.make_pair()
    con_a, con_b = InMemoryChannel.make_pair()

    for i in range(10):
        q = pro_b._out_q if (i % 2 == 0) else con_b._out_q  # type: ignore[attr-defined]
        q.put(_make_move_envelope("a valid argument for the motion"))

    real_brain = SimpleRefereeBrain()
    call_log: list[str] = []
    original_decide = real_brain.decide

    def _counting_decide(ctx):
        call_log.append(ctx.request_kind)
        return original_decide(ctx)

    real_brain.decide = _counting_decide  # type: ignore[method-assign]

    loop = DebateGameLoop(
        match_id="count-test",
        engine=_make_engine(),
        brain=real_brain,
        channels={"PRO": pro_a, "CON": con_a},
        move_timeout_seconds=5.0,
        rubric=RUBRIC,
    )
    state = loop.run()

    evaluate_calls = sum(1 for k in call_log if k == "evaluate_turn")
    verdict_calls = sum(1 for k in call_log if k == "render_verdict")
    scored_turns = sum(1 for r in state.transcript if r.referee_flag != "retry_exhausted")

    assert verdict_calls == 1, "Exactly one RENDER_VERDICT call"
    assert evaluate_calls == scored_turns, "One EVALUATE_TURN per scored turn, no pre-turn calls"
    assert evaluate_calls + verdict_calls == len(call_log)
