"""Referee server coordinating matchmaking and game loop (T4.9)."""
from __future__ import annotations

import logging
import threading
import uuid
from pathlib import Path
from typing import Any

from agent_arena.constants import PROTOCOL_VERSION
from agent_arena.services.game.debate_state import DebateState
from agent_arena.services.protocol.codec import decode
from agent_arena.services.protocol.message_types import ErrorCode, MessageType
from agent_arena.services.protocol.validation import (
    ProtocolVersionError,
    UnknownMessageTypeError,
    ValidationError,
    validate,
)
from agent_arena.services.referee._turn_runner import recv_timed
from agent_arena.services.referee.brain.base import RefereeBrain
from agent_arena.services.referee.brain.simple_brain import SimpleRefereeBrain
from agent_arena.services.referee.game_loop import DebateGameLoop
from agent_arena.services.referee.matchmaking import setup_match
from agent_arena.services.referee.server_helpers import (
    build_debate_engine,
    load_evidence_pack,
    send_referee_message,
)
from agent_arena.shared.config import SetupConfig
from agent_arena.shared.heartbeat import HeartbeatSender
from agent_arena.shared.shutdown import ShutdownCoordinator
from agent_arena.shared.transport.channel import Channel, FramedChannel
from agent_arena.shared.transport.tcp_server import TcpServer
from agent_arena.shared.watchdog import WatchdogThread

logger = logging.getLogger(__name__)


class RefereeServer:
    """Listens for connections, registers players, and runs the game loop (T4.9)."""

    def __init__(
        self,
        config: SetupConfig,
        brain: RefereeBrain | None = None,
        coordinator: ShutdownCoordinator | None = None,
    ) -> None:
        self.config = config
        self.brain = brain or SimpleRefereeBrain()
        self.coordinator = coordinator or ShutdownCoordinator()
        self.server = TcpServer(
            config.network.host,
            config.network.port,
            config.network.player_count,
            self.on_connect,
            self.on_reject,
        )
        self.registered_players: dict[str, Channel] = {}
        self.lock = threading.Lock()
        self.game_thread: threading.Thread | None = None
        self.final_state: DebateState | None = None
        self.exception: Exception | None = None
        self.match_id: str | None = None
        self.watchdog = WatchdogThread(
            timeout_seconds=config.network.read_timeout_seconds,
            on_timeout=self._on_watchdog_timeout,
        )
        self.heartbeat_senders: dict[str, HeartbeatSender] = {}
        self._heartbeat_seq = 0
        self.coordinator.register_callback(self.stop)

    def start(self) -> None:
        self.watchdog.start()
        self.server.start()

    def stop(self) -> None:
        import contextlib

        self.server.stop()
        self.watchdog.stop()
        for sender in self.heartbeat_senders.values():
            sender.stop()
        with self.lock:
            channels = list(self.registered_players.values())
        for ch in channels:
            with contextlib.suppress(Exception):
                ch.close()

    def _next_heartbeat_seq(self) -> int:
        with self.lock:
            self._heartbeat_seq += 1
            return self._heartbeat_seq

    def _on_watchdog_timeout(self, player_id: str) -> None:
        self.coordinator.request_shutdown(f"watchdog:player_timeout:{player_id}")

    def _start_heartbeat_sender(self, player_id: str, ch: Channel) -> None:
        def _send() -> None:
            if self.match_id is None:
                return
            send_referee_message(
                ch,
                self.match_id,
                MessageType.HEARTBEAT,
                {},
                self._next_heartbeat_seq(),
            )

        sender = HeartbeatSender(
            interval_seconds=self.config.game.heartbeat_interval_seconds,
            send_fn=_send,
            shutdown_event=self.coordinator._event,
        )
        self.heartbeat_senders[player_id] = sender
        sender.start()

    def _send_error(self, ch: Channel, message: str, code: str = ErrorCode.MALFORMED_MESSAGE) -> None:
        send_referee_message(
            ch,
            None,
            MessageType.ERROR,
            {"code": code, "message": message},
            1,
        )

    def on_reject(self, ch: Channel) -> None:
        framed_ch = FramedChannel(ch, self.config.framing.max_frame_size_bytes)
        self._send_error(framed_ch, "Match is full", code=ErrorCode.MATCH_FULL)

    def on_connect(self, ch: Channel) -> None:
        try:
            framed_ch = FramedChannel(ch, self.config.framing.max_frame_size_bytes)
            raw = recv_timed(framed_ch, self.config.network.read_timeout_seconds)
            if not raw:
                framed_ch.close()
                return
            env = decode(raw)
            try:
                validate(env, PROTOCOL_VERSION)
            except ProtocolVersionError:
                self._send_error(framed_ch, "Protocol version mismatch", code=ErrorCode.VERSION_MISMATCH)
                framed_ch.close()
                return
            except (UnknownMessageTypeError, ValidationError):
                self._send_error(framed_ch, "Malformed message", code=ErrorCode.MALFORMED_MESSAGE)
                framed_ch.close()
                return

            if env.type != MessageType.REGISTER:
                self._send_error(framed_ch, "Expected REGISTER", code=ErrorCode.UNEXPECTED_MESSAGE)
                framed_ch.close()
                return
            player_id = env.sender
            if not player_id:
                framed_ch.close()
                return
            with self.lock:
                if player_id in self.registered_players:
                    framed_ch.close()
                    return
                self.registered_players[player_id] = framed_ch
                self.watchdog.register(player_id)
                self._start_heartbeat_sender(player_id, framed_ch)
                if len(self.registered_players) == self.config.network.player_count:
                    self.game_thread = threading.Thread(target=self.run_game, daemon=True)
                    self.game_thread.start()
        except Exception:
            logger.exception("Error in referee server on_connect")
            ch.close()

    def _broadcast(self, match_id: str, m_type: MessageType, payload: dict[str, Any], seq: int) -> None:
        for ch in self.registered_players.values():
            send_referee_message(ch, match_id, m_type, payload, seq)

    def run_game(self) -> None:
        try:
            match_id = str(uuid.uuid4())
            self.match_id = match_id
            player_ids = list(self.registered_players.keys())
            pack_id = self.config.debate.match.evidence_pack
            evidence_pack = load_evidence_pack(pack_id)

            ms = setup_match(
                match_id=match_id,
                player_ids=player_ids,
                seed=self.config.debate.match.seed,
                motion=self.config.debate.match.motion,
                weights=self.config.debate.judge.weights,
                format_cfg=self.config.debate.format.model_dump(),
                evidence_pack=evidence_pack,
                judge_variant=self.config.debate.judge.variant,
            )
            pro_pid = [pid for pid, side in ms.side_map.items() if side == "PRO"][0]
            con_pid = [pid for pid, side in ms.side_map.items() if side == "CON"][0]

            self._broadcast(match_id, MessageType.REGISTER_ACK, {"match_id": match_id}, 1)
            for pid, ch in self.registered_players.items():
                send_referee_message(
                    ch,
                    match_id,
                    MessageType.ROLE_ASSIGN,
                    {"role": ms.side_map[pid], "game_config": ms.game_config},
                    2,
                )

            engine = build_debate_engine(self.config)
            loop = DebateGameLoop(
                match_id=match_id,
                engine=engine,
                brain=self.brain,
                channels={"PRO": self.registered_players[pro_pid], "CON": self.registered_players[con_pid]},
                move_timeout_seconds=self.config.game.move_timeout_seconds,
                rubric={"weights": self.config.debate.judge.weights},
                evidence_pack=evidence_pack,
                judge_variant=self.config.debate.judge.variant,
                results_dir=Path(self.config.debate.match.results_dir),
            )
            self.final_state = loop.run()
        except Exception as e:
            self.exception = e
            logger.exception("Error in run_game")
        finally:
            self.coordinator.request_shutdown("game_over")
