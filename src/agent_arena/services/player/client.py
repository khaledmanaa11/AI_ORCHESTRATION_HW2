"""Player connection client (T5.4)."""
from __future__ import annotations

import contextlib
import logging
from typing import Any

from agent_arena.services.player.agent import PlayerAgent
from agent_arena.services.protocol.message_types import MessageType
from agent_arena.shared.config import FramingConfig, GameConfig, NetworkConfig
from agent_arena.shared.heartbeat import HeartbeatSender
from agent_arena.shared.shutdown import ShutdownCoordinator
from agent_arena.shared.transport.tcp_client import TcpClient
from agent_arena.shared.watchdog import WatchdogThread

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
        max_retries: int | None = None,
        backoff_base: float | None = None,
        config: Any = None,
        coordinator: ShutdownCoordinator | None = None,
    ) -> None:
        network_config = getattr(config, "network", None) or NetworkConfig(host=host, port=port)
        framing_config = getattr(config, "framing", None) or FramingConfig()
        game_config = getattr(config, "game", None) or GameConfig()
        self.player_id = player_id
        self.host = host
        self.port = port
        self.connect_timeout = connect_timeout
        self.seed = seed
        self.max_retries = max_retries if max_retries is not None else network_config.max_retries
        self.backoff_base = backoff_base if backoff_base is not None else network_config.backoff_base
        self.max_frame_size_bytes = framing_config.max_frame_size_bytes
        self.heartbeat_interval_seconds = game_config.heartbeat_interval_seconds
        self.config = config
        self.coordinator = coordinator or ShutdownCoordinator()
        self.watchdog = WatchdogThread(
            timeout_seconds=network_config.read_timeout_seconds,
            on_timeout=self._on_watchdog_timeout,
        )
        self.heartbeat_sender: HeartbeatSender | None = None
        self.client: TcpClient | None = None
        self.agent: PlayerAgent | None = None
        self.coordinator.register_callback(self.close)

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
        framed_ch = FramedChannel(ch, self.max_frame_size_bytes)
        self.agent = PlayerAgent(
            self.player_id,
            framed_ch,
            self.seed,
            config=self.config,
            coordinator=self.coordinator,
            watchdog=self.watchdog,
        )
        self.watchdog.register("referee")
        self.watchdog.start()
        self._start_heartbeat_sender()
        try:
            self.agent.run()
        finally:
            if not self.coordinator.is_shutdown():
                self.coordinator.request_shutdown("player_client_stopped")

    def close(self) -> None:
        self.watchdog.stop()
        if self.heartbeat_sender:
            self.heartbeat_sender.stop()
        if self.client:
            self.client.close()
        if self.agent and hasattr(self.agent.channel, "close"):
            with contextlib.suppress(Exception):
                self.agent.channel.close()

    def _on_watchdog_timeout(self, peer: str) -> None:
        self.coordinator.request_shutdown(f"watchdog:{peer}_timeout")

    def _start_heartbeat_sender(self) -> None:
        def _send() -> None:
            if self.agent is not None:
                self.agent._send(MessageType.HEARTBEAT, {})

        self.heartbeat_sender = HeartbeatSender(
            interval_seconds=self.heartbeat_interval_seconds,
            send_fn=_send,
            shutdown_event=self.coordinator._event,
        )
        self.heartbeat_sender.start()
