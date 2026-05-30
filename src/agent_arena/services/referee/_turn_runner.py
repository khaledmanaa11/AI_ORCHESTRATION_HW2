"""Inner per-turn execution: recv loop, two-tier legality, retry/timeout policy."""
from __future__ import annotations

import logging
import queue
import threading
import time
from collections.abc import Callable
from typing import Any

from agent_arena.constants import (
    ERROR_ILLEGAL_MOVE,
    ERROR_MALFORMED_MESSAGE,
    FLAG_QUOTA_ABORTED,
)
from agent_arena.services.game.debate_engine import DebateEngine
from agent_arena.services.game.debate_state import DebateState
from agent_arena.services.game.debate_state import active_side as _aside
from agent_arena.services.protocol.codec import CodecError, decode
from agent_arena.services.protocol.message_types import MessageType
from agent_arena.services.referee.brain.base import (
    RefereeBrain,
    RefereeContext,
    RequestKind,
)
from agent_arena.shared.transport.channel import Channel, ConnectionClosedError

logger = logging.getLogger(__name__)

SendFn = Callable[[str, MessageType, dict], None]
BcastFn = Callable[[MessageType, dict], None]


class DisconnectError(Exception):
    """Raised when a player connection is lost mid-turn."""


class QuotaAbortedError(Exception):
    """Raised when a player reports API quota exhaustion mid-turn."""


def recv_timed(ch: Channel, timeout: float) -> bytes | None:
    """Receive one frame within *timeout* seconds; returns None on expiry."""
    buf: queue.Queue[tuple[str, Any]] = queue.Queue()

    def _w() -> None:
        try:
            buf.put(("ok", ch.recv()))
        except Exception as exc:  # noqa: BLE001
            buf.put(("err", exc))

    threading.Thread(target=_w, daemon=True).start()
    try:
        tag, val = buf.get(timeout=timeout)
    except queue.Empty:
        return None
    if tag == "err":
        raise val  # type: ignore[misc]
    return val  # type: ignore[return-value]


def _make_ctx(
    kind: RequestKind,
    state: DebateState,
    move: dict | None,
    rubric: dict,
    judge_variant: str,
    evidence_pack: dict,
    trajectory: list,
) -> RefereeContext:
    return RefereeContext(kind, state.to_dict(), move, rubric,
                          judge_variant, evidence_pack, list(trajectory))


def _heartbeat_watchdog(channels: dict[str, Channel], side: str) -> None:
    ch = channels[side]
    watchdog = getattr(ch, "_arena_watchdog", None)
    player_id = getattr(ch, "_arena_player_id", None)
    if watchdog is not None and player_id is not None:
        watchdog.heartbeat(player_id)


def run_turn(  # noqa: C901
    state: DebateState,
    engine: DebateEngine,
    brain: RefereeBrain,
    channels: dict[str, Channel],
    move_timeout: float,
    trajectory: list[dict[str, Any]],
    rubric: dict[str, Any],
    evidence_pack: dict[str, Any],
    judge_variant: str,
    send_fn: SendFn,
    bcast_fn: BcastFn,
) -> DebateState:
    """Execute one turn with retry gate, timeout, and fault handling (E1–E6)."""
    snap = state.rules_snapshot
    t = state.turn_number + 1
    side = _aside(t, snap.get("first_speaker", "PRO"))
    cap: int = int(snap.get("retry_cap", 1))
    lm = engine.get_legal_moves(state)
    t0 = time.monotonic()
    attempt, want_req = 0, True

    while True:
        remaining = max(move_timeout - (time.monotonic() - t0), 0.0)
        if want_req:
            lm[0] = {**lm[0], "attempt": attempt}
            send_fn(side, MessageType.MOVE_REQUEST,
                    {"state": state.to_dict(), "legal_moves": lm,
                     "move_timeout_seconds": remaining})
            want_req = False

        remaining = max(move_timeout - (time.monotonic() - t0), 0.0)
        try:
            raw = recv_timed(channels[side], remaining)
        except ConnectionClosedError as exc:
            raise DisconnectError from exc

        if raw is None:                                           # timeout → penalised skip
            return engine.apply_move(state, {"text": ""}, flag="timeout", retry_count=attempt)

        _heartbeat_watchdog(channels, side)

        try:
            env = decode(raw)
        except CodecError:                                        # bad content → drop frame
            send_fn(side, MessageType.ERROR,
                    {"code": ERROR_MALFORMED_MESSAGE, "message": "malformed"})
            continue

        if env.type != MessageType.MOVE_SUBMIT:
            send_fn(side, MessageType.ERROR,
                    {"code": ERROR_MALFORMED_MESSAGE, "message": "unexpected_type"})
            continue

        move_payload = env.payload.get("move", {})
        move: dict[str, Any] = move_payload if isinstance(move_payload, dict) else {}
        flag = env.payload.get("flag", move.get("flag"))
        if flag == FLAG_QUOTA_ABORTED:
            raise QuotaAbortedError

        ok, reason = engine.validate_move(state, move)           # Tier-1 mechanical
        if not ok:
            send_fn(side, MessageType.ERROR,
                    {"code": ERROR_ILLEGAL_MOVE, "message": reason})
            attempt += 1
            if attempt > cap:
                return engine.apply_move(
                    state, {"text": ""}, flag="retry_exhausted", retry_count=attempt)
            want_req = True
            continue

        ctx = _make_ctx(RequestKind.EVALUATE_TURN, state, move,   # Tier-2 semantic
                        rubric, judge_variant, evidence_pack, trajectory)
        d = brain.decide(ctx)
        if not d.legal:
            send_fn(side, MessageType.ERROR,
                    {"code": ERROR_ILLEGAL_MOVE, "message": d.flag or "illegal"})
            attempt += 1
            if attempt > cap:
                return engine.apply_move(
                    state, {"text": ""}, flag="retry_exhausted", retry_count=attempt)
            want_req = True
            continue

        if d.turn_scores:
            trajectory.append({"side": side, "turn_scores": d.turn_scores,
                                "word_count": len(move.get("text", "").split())})
        new_state = engine.apply_move(state, move, tell=d.tell, flag=d.flag,
                                      retry_count=attempt)
        total = int(snap.get("total_turns", 10))
        nt = new_state.turn_number + 1
        next_side = _aside(nt, snap.get("first_speaker", "PRO")) if nt <= total else side
        bcast_fn(MessageType.STATE_UPDATE,
                 {"state": new_state.to_dict(), "last_move": move,
                  "active_player": next_side})
        return new_state
