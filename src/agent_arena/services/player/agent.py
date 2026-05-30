"""Player agent message handler (T5.3, Module P7)."""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Any

from agent_arena.constants import FLAG_QUOTA_ABORTED, PROTOCOL_VERSION
from agent_arena.services.player.brain.seeded_brain import SeededPlayerBrain
from agent_arena.services.protocol.codec import decode, encode
from agent_arena.services.protocol.envelope import Envelope
from agent_arena.services.protocol.message_types import MessageType
from agent_arena.shared.api_gatekeeper import GatekeeperError
from agent_arena.shared.shutdown import ShutdownCoordinator
from agent_arena.shared.transport.channel import Channel
from agent_arena.shared.watchdog import WatchdogThread

logger = logging.getLogger(__name__)


def _get_val(obj: Any, keys: list[str], default: Any) -> Any:
    curr = obj
    for k in keys:
        curr = curr.get(k) if isinstance(curr, dict) else getattr(curr, k, None)
        if curr is None:
            return default
    return curr


class PlayerAgent:
    """Manages player side communication loop (T5.3, P7)."""

    def __init__(
        self,
        player_id: str,
        channel: Channel,
        seed: int,
        config: Any = None,
        brain: Any = None,
        coordinator: ShutdownCoordinator | None = None,
        watchdog: WatchdogThread | None = None,
    ) -> None:
        self.player_id, self.channel, self.seed = player_id, channel, seed
        self.match_id, self.role, self.game_config, self.brain = None, None, None, brain
        self.game_over, self.seq = False, 0
        self.coordinator = coordinator
        self.watchdog = watchdog
        self._send_lock = threading.Lock()
        self.scratchpad: list[Any] = []
        self.trace_buffer: list[dict[str, Any]] = []
        self.config = config
        if self.config is None:
            try:
                from agent_arena.shared.config import load_setup_config
                self.config = load_setup_config("config/setup.json")
            except Exception:
                pass

    def _send(self, t: MessageType, payload: dict[str, Any]) -> None:
        with self._send_lock:
            self.seq += 1
            env = Envelope(
                protocol_version=PROTOCOL_VERSION,
                type=t,
                match_id=self.match_id,
                sender=self.player_id,
                seq=self.seq,
                timestamp=datetime.now(timezone.utc).isoformat(),
                payload=payload,
            )
            self.channel.send(encode(env))

    def _request_shutdown(self, reason: str) -> None:
        if self.coordinator is not None:
            self.coordinator.request_shutdown(reason)

    def _is_shutdown(self) -> bool:
        return self.coordinator is not None and self.coordinator.is_shutdown()

    def run(self) -> None:
        self._send(MessageType.REGISTER, {})
        while not self.game_over and not self._is_shutdown():
            try:
                raw = self.channel.recv()
                if not raw:
                    self._request_shutdown("connection_closed")
                    break
                if self.watchdog is not None:
                    self.watchdog.heartbeat("referee")
                self.handle_message(decode(raw))
            except Exception as e:
                logger.error("Player agent %s exception: %s", self.player_id, e)
                self._request_shutdown("player_exception")
                break

    def handle_message(self, env: Envelope) -> None:
        t, payload = env.type, env.payload or {}
        if t == MessageType.REGISTER_ACK:
            self.match_id = payload.get("match_id")
        elif t == MessageType.ROLE_ASSIGN:
            self.role = payload.get("role")
            self.game_config = payload.get("game_config") or {}
            if self.role and not self.brain:
                choice = _get_val(self.config, ["debate", "player", "brain_choice"], "seeded")
                if choice == "llm":
                    from agent_arena.services.player.brain.llm_brain import LLMPlayerBrain
                    from agent_arena.shared.llm_client import LLMClient
                    gatekeeper = _get_val(self.config, ["api_gatekeeper"], None)
                    provider = _get_val(self.config, ["llm", "provider"], None)
                    self.brain = LLMPlayerBrain(
                        client=LLMClient(provider=provider, gatekeeper=gatekeeper),
                        config=self.config,
                    )
                else:
                    self.brain = SeededPlayerBrain(self.seed, self.role)
        elif t == MessageType.MOVE_REQUEST:
            state, gc = payload.get("state", {}), self.game_config or {}
            ablation = _get_val(self.config, ["debate", "player", "ablation"], {})
            if hasattr(ablation, "model_dump"):
                ablation = ablation.model_dump()
            if self.brain:
                if hasattr(self.brain, "generate"):
                    from agent_arena.services.player.brain.base import PlayerContext
                    state_with_id = dict(state)
                    if "match_id" not in state_with_id and self.match_id:
                        state_with_id["match_id"] = self.match_id
                    ctx = PlayerContext(
                        state=state_with_id,
                        legal_moves=payload.get("legal_moves", []),
                        rubric=gc.get("rubric", {}),
                        evidence_pack=gc.get("evidence_pack", {}),
                        side=self.role or "PRO",
                        ablation=ablation,
                        scratchpad=self.scratchpad,
                        seed=self.seed,
                    )
                    try:
                        dec = self.brain.generate(ctx)
                    except GatekeeperError as exc:
                        logger.warning(
                            "Player %s aborting move generation: %s",
                            self.player_id,
                            exc,
                        )
                        self._send(
                            MessageType.MOVE_SUBMIT,
                            {"move": {"text": ""}, "flag": FLAG_QUOTA_ABORTED},
                        )
                        self.game_over = True
                        self._request_shutdown("quota_aborted")
                        return
                    move, trace = dec.move, dec.trace
                    if trace:
                        self.trace_buffer.append(trace)
                        for k in ("reflexion_lesson", "read_profile"):
                            if trace.get(k):
                                self.scratchpad.append(trace[k])
                else:
                    move = {"text": self.brain.generate_utterance(state.get("turn_number", 0) + 1)}
            else:
                move = {"text": "No brain initialized."}
            self._send(MessageType.MOVE_SUBMIT, {"move": move})
        elif t == MessageType.ERROR:
            logger.error("Player %s received ERROR: %s", self.player_id, payload)
            self.game_over = True
            self._request_shutdown("error")
        elif t == MessageType.GAME_OVER:
            self.game_over = True
            if self.trace_buffer:
                pc = _get_val(self.config, ["debate", "player", "private_capture"], True)
                rid = _get_val(self.config, ["debate", "match", "run_id"], "run_001")
                rdir = _get_val(self.config, ["debate", "match", "results_dir"], "results")
                from agent_arena.services.player.brain.capture import dump
                dump(self.trace_buffer, rid, rdir, self.match_id or "unknown", self.role or "unknown", pc)
            self._request_shutdown("game_over")
