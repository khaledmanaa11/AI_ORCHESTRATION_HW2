"""Player agent message handler (T5.3)."""
from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from agent_arena.services.player.brain.seeded_brain import SeededPlayerBrain
from agent_arena.services.protocol.codec import decode, encode
from agent_arena.services.protocol.envelope import Envelope
from agent_arena.services.protocol.message_types import MessageType
from agent_arena.shared.transport.channel import Channel

logger = logging.getLogger(__name__)


class PlayerAgent:
    """Manages player side communication loop (T5.3)."""

    def __init__(self, player_id: str, channel: Channel, seed: int) -> None:
        self.player_id = player_id
        self.channel = channel
        self.seed = seed
        self.match_id: str | None = None
        self.role: str | None = None
        self.game_config: dict[str, Any] | None = None
        self.brain: SeededPlayerBrain | None = None
        self.game_over = False
        self.seq = 0

    def _send(self, t: MessageType, payload: dict[str, Any]) -> None:
        self.seq += 1
        env = Envelope(
            protocol_version="1.00",
            type=t,
            match_id=self.match_id,
            sender=self.player_id,
            seq=self.seq,
            timestamp=datetime.now(timezone.utc).isoformat(),
            payload=payload,
        )
        self.channel.send(encode(env))

    def run(self) -> None:
        """Main message-handling loop."""
        self._send(MessageType.REGISTER, {})

        while not self.game_over:
            try:
                raw = self.channel.recv()
                if not raw:
                    break
                env = decode(raw)
                self.handle_message(env)
            except Exception as e:
                logger.error("Player agent %s exception: %s", self.player_id, e)
                break

    def handle_message(self, env: Envelope) -> None:
        t = env.type
        payload = env.payload or {}

        if t == MessageType.REGISTER_ACK:
            self.match_id = payload.get("match_id")

        elif t == MessageType.ROLE_ASSIGN:
            self.role = payload.get("role")
            self.game_config = payload.get("game_config")
            if self.role:
                self.brain = SeededPlayerBrain(self.seed, self.role)

        elif t == MessageType.GAME_START:
            pass

        elif t == MessageType.MOVE_REQUEST:
            state = payload.get("state", {})
            turn_number = state.get("turn_number", 0) + 1
            if self.brain:
                utterance = self.brain.generate_utterance(turn_number)
            else:
                utterance = "No brain initialized."
            self._send(MessageType.MOVE_SUBMIT, {"move": {"text": utterance}})

        elif t == MessageType.STATE_UPDATE:
            pass

        elif t == MessageType.ERROR:
            logger.error("Player %s received ERROR: %s", self.player_id, payload)

        elif t == MessageType.GAME_OVER:
            self.game_over = True
