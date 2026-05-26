"""Player connection client (T5.4)."""
from __future__ import annotations

import logging

from agent_arena.services.player.agent import PlayerAgent
from agent_arena.shared.transport.tcp_client import TcpClient

logger = logging.getLogger(__name__)


class PlayerClient:
    """Manages the connection and lifecycle of a player (T5.4)."""

    def __init__(
        self,
        player_id: str,
        host: str,
        port: int,
        connect_timeout: float,
        seed: int,
        max_retries: int = 5,
        backoff_base: float = 0.1,
    ) -> None:
        self.player_id = player_id
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.seed = seed
        self.max_retries = max_retries
        self.backoff_base = backoff_base
        self.client: TcpClient | None = None
        self.agent: PlayerAgent | None = None

    def start(self) -> None:
        """Connect to TCP server and run player agent."""
        self.client = TcpClient(
            self.host,
            self.port,
            self.connect_timeout,
            self.max_retries,
            self.backoff_base,
        )
        ch = self.client.connect()
        from agent_arena.shared.transport.channel import FramedChannel
        framed_ch = FramedChannel(ch)
        self.agent = PlayerAgent(self.player_id, framed_ch, self.seed)
        self.agent.run()

    def close(self) -> None:
        if self.client:
            self.client.close()
