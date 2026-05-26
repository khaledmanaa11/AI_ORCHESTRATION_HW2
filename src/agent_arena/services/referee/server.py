"""Referee server coordinating matchmaking and game loop (T4.9)."""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from typing import Any

from agent_arena.constants import PROTOCOL_VERSION
from agent_arena.services.game.debate_engine import DebateEngine
from agent_arena.services.game.debate_state import DebateState
from agent_arena.services.protocol.codec import decode, encode
from agent_arena.services.protocol.envelope import Envelope
from agent_arena.services.protocol.message_types import MessageType
from agent_arena.services.referee._turn_runner import recv_timed
from agent_arena.services.referee.brain.base import RefereeBrain
from agent_arena.services.referee.brain.simple_brain import SimpleRefereeBrain
from agent_arena.services.referee.game_loop import DebateGameLoop
from agent_arena.services.referee.matchmaking import setup_match
from agent_arena.shared.config import SetupConfig
from agent_arena.shared.transport.channel import Channel, FramedChannel
from agent_arena.shared.transport.tcp_server import TcpServer

logger = logging.getLogger(__name__)


class RefereeServer:
    """Listens for connections, registers players, and runs the game loop (T4.9)."""

    def __init__(self, config: SetupConfig, brain: RefereeBrain | None = None) -> None:
        self.config = config
        self.brain = brain or SimpleRefereeBrain()
        self.server = TcpServer(
            config.network.host,
            config.network.port,
            config.network.player_count,
            self.on_connect,
        )
        self.registered_players: dict[str, Channel] = {}
        self.lock = threading.Lock()
        self.game_thread: threading.Thread | None = None
        self.final_state: DebateState | None = None
        self.exception: Exception | None = None

    def start(self) -> None:
        self.server.start()

    def stop(self) -> None:
        import contextlib

        self.server.stop()
        with self.lock:
            for ch in self.registered_players.values():
                with contextlib.suppress(Exception):
                    ch.close()

    def _send_error(self, ch: Channel, message: str) -> None:
        err = Envelope(
            protocol_version=PROTOCOL_VERSION,
            type=MessageType.ERROR,
            match_id=None,
            sender="referee",
            seq=1,
            timestamp=datetime.now(timezone.utc).isoformat(),
            payload={"code": "MALFORMED_MESSAGE", "message": message},
        )
        ch.send(encode(err))

    def on_connect(self, ch: Channel) -> None:
        try:
            framed_ch = FramedChannel(ch, self.config.framing.max_frame_size_bytes)
            raw = recv_timed(framed_ch, self.config.network.read_timeout_seconds)
            if not raw:
                framed_ch.close()
                return
            env = decode(raw)
            if env.type != MessageType.REGISTER:
                self._send_error(framed_ch, "Expected REGISTER")
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
                if len(self.registered_players) == self.config.network.player_count:
                    self.game_thread = threading.Thread(target=self.run_game, daemon=True)
                    self.game_thread.start()
        except Exception:
            logger.exception("Error in referee server on_connect")
            ch.close()

    def _broadcast(self, match_id: str, m_type: MessageType, payload: dict[str, Any], seq: int) -> None:
        for ch in self.registered_players.values():
            env = Envelope(
                protocol_version=PROTOCOL_VERSION,
                type=m_type,
                match_id=match_id,
                sender="referee",
                seq=seq,
                timestamp=datetime.now(timezone.utc).isoformat(),
                payload=payload,
            )
            ch.send(encode(env))

    def run_game(self) -> None:
        try:
            match_id = str(uuid.uuid4())
            player_ids = list(self.registered_players.keys())
            ms = setup_match(
                match_id=match_id,
                player_ids=player_ids,
                seed=self.config.debate.match.seed,
                motion=self.config.debate.match.motion,
                weights=self.config.debate.judge.weights,
                format_cfg=self.config.debate.format.model_dump(),
                evidence_pack={"pack_id": self.config.debate.match.evidence_pack},
                judge_variant=self.config.debate.judge.variant,
            )
            pro_pid = [pid for pid, side in ms.side_map.items() if side == "PRO"][0]
            con_pid = [pid for pid, side in ms.side_map.items() if side == "CON"][0]

            self._broadcast(match_id, MessageType.REGISTER_ACK, {"match_id": match_id}, 1)
            for pid, ch in self.registered_players.items():
                env = Envelope(
                    protocol_version=PROTOCOL_VERSION,
                    type=MessageType.ROLE_ASSIGN,
                    match_id=match_id,
                    sender="referee",
                    seq=2,
                    timestamp=datetime.now(timezone.utc).isoformat(),
                    payload={"role": ms.side_map[pid], "game_config": ms.game_config},
                )
                ch.send(encode(env))

            engine = DebateEngine({
                "r": self.config.debate.format.rebuttal_rounds,
                "word_cap": self.config.debate.format.word_cap,
                "retry_cap": self.config.debate.format.retry_cap,
                "first_speaker": self.config.debate.format.first_speaker,
                "motion": self.config.debate.match.motion,
            })
            loop = DebateGameLoop(
                match_id=match_id,
                engine=engine,
                brain=self.brain,
                channels={"PRO": self.registered_players[pro_pid], "CON": self.registered_players[con_pid]},
                move_timeout_seconds=self.config.game.move_timeout_seconds,
                rubric={"weights": self.config.debate.judge.weights},
                evidence_pack={"pack_id": self.config.debate.match.evidence_pack},
                judge_variant=self.config.debate.judge.variant,
            )
            self.final_state = loop.run()
        except Exception as e:
            self.exception = e
            logger.exception("Error in run_game")
