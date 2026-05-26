"""Debate game-loop orchestrator: GAME_START → turns → GAME_OVER (S3, S8, FR-FT7)."""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_arena.constants import PROTOCOL_VERSION, TERMINATED_ABORTED, TERMINATED_DISCONNECT
from agent_arena.services.game.debate_engine import DebateEngine
from agent_arena.services.game.debate_state import DebateState
from agent_arena.services.protocol.codec import encode
from agent_arena.services.protocol.envelope import Envelope
from agent_arena.services.protocol.message_types import MessageType
from agent_arena.services.referee._turn_runner import (
    DisconnectError,
    run_turn,
)
from agent_arena.services.referee.brain.base import (
    RefereeBrain,
    RefereeContext,
    RequestKind,
    aggregate_verdict,
)
from agent_arena.services.referee.brain.simple_brain import simple_tiebreak
from agent_arena.services.referee.result import write_trajectory
from agent_arena.shared.transport.channel import Channel

logger = logging.getLogger(__name__)


def _enc(match_id: str, t: MessageType, payload: dict[str, Any], seq: int) -> bytes:
    return encode(Envelope(
        protocol_version=PROTOCOL_VERSION,
        type=t,
        match_id=match_id,
        sender="referee",
        seq=seq,
        timestamp=datetime.now(timezone.utc).isoformat(),
        payload=payload,
    ))


@dataclass
class DebateGameLoop:
    """Guarantees exactly one GAME_OVER after GAME_START (FR-FT7, REF-010)."""

    match_id: str
    engine: DebateEngine
    brain: RefereeBrain
    channels: dict[str, Channel]        # {"PRO": ch, "CON": ch}
    move_timeout_seconds: float
    rubric: dict[str, Any] = field(default_factory=dict)
    evidence_pack: dict[str, Any] = field(default_factory=dict)
    judge_variant: str = "naive"
    results_dir: Path | None = None
    _seq: int = field(default=0, init=False, repr=False)
    _traj: list[dict[str, Any]] = field(default_factory=list, init=False, repr=False)

    # ------------------------------------------------------------------ helpers
    def _nxt(self) -> int:
        self._seq += 1
        return self._seq

    def _send(self, side: str, t: MessageType, p: dict[str, Any]) -> None:
        self.channels[side].send(_enc(self.match_id, t, p, self._nxt()))

    def _bcast(self, t: MessageType, p: dict[str, Any]) -> None:
        for s in ("PRO", "CON"):
            self._send(s, t, p)

    def _ctx(self, kind: RequestKind, state: DebateState, move: dict | None) -> RefereeContext:
        return RefereeContext(kind, state.to_dict(), move, self.rubric,
                              self.judge_variant, self.evidence_pack, list(self._traj))

    # ------------------------------------------------------------------ main
    def run(self) -> DebateState:
        """Run the full match; every path after GAME_START reaches one GAME_OVER."""
        state = self.engine.get_initial_state()
        snap = state.rules_snapshot
        fs = snap.get("first_speaker", "PRO")
        other = "CON" if fs == "PRO" else "PRO"
        self._bcast(MessageType.GAME_START,
                    {"initial_state": state.to_dict(), "turn_order": [fs, other]})
        terminated: str | None = None
        try:
            state = self._run_turns(state)
        except DisconnectError:
            terminated = TERMINATED_DISCONNECT
            state = self._forced_verdict(state, terminated)
        except Exception:
            logger.exception("Unexpected abort in match=%s", self.match_id)
            terminated = TERMINATED_ABORTED
            state = self._forced_verdict(state, terminated)
        finally:
            self._finish(state, terminated)
        return state

    def _run_turns(self, state: DebateState) -> DebateState:
        while not self.engine.is_terminal(state):
            state = run_turn(
                state, self.engine, self.brain, self.channels,
                self.move_timeout_seconds, self._traj, self.rubric,
                self.evidence_pack, self.judge_variant,
                self._send, self._bcast,
            )
        d = self.brain.decide(self._ctx(RequestKind.RENDER_VERDICT, state, None))
        return DebateState(state.motion, state.turn_number, state.transcript,
                           "COMPLETE", d.verdict or {}, state.rules_snapshot)

    def _forced_verdict(self, state: DebateState, reason: str) -> DebateState:
        """Compute verdict on partial transcript; never raises (FR-SB6, 8.3/8.6)."""
        try:
            d = self.brain.decide(self._ctx(RequestKind.RENDER_VERDICT, state, None))
            verdict: dict[str, Any] = d.verdict or {}
        except Exception:
            verdict = aggregate_verdict(
                self._traj, self.rubric.get("weights", {}), simple_tiebreak)
        verdict["terminated_reason"] = reason
        return DebateState(state.motion, state.turn_number, state.transcript,
                           "COMPLETE", verdict, state.rules_snapshot)

    def _finish(self, state: DebateState, _terminated: str | None) -> None:
        """Broadcast GAME_OVER + dump trajectory — always called from finally."""
        v = state.verdict or {}
        try:
            self._bcast(MessageType.GAME_OVER,
                        {"result": v.get("winner", "PRO"),
                         "reason": v.get("rationale", ""),
                         "final_state": state.to_dict()})
        except Exception:
            logger.exception("GAME_OVER broadcast failed for match=%s", self.match_id)
        write_trajectory(self.match_id, self._traj, self.results_dir)
