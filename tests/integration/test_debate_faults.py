"""Integration tests for debate loop faults and timeouts (RH2.3)."""
from __future__ import annotations

import threading
import time
from typing import Any

from agent_arena.services.player.agent import PlayerAgent
from agent_arena.services.player.client import PlayerClient
from agent_arena.services.protocol.envelope import Envelope
from agent_arena.services.protocol.message_types import MessageType
from agent_arena.services.referee.server import RefereeServer
from agent_arena.shared.config import load_setup_config
from agent_arena.shared.transport.tcp_client import TcpClient


class FaultPlayerAgent(PlayerAgent):
    """Player agent that can inject timeouts or disconnects."""

    def __init__(
        self,
        *args: Any,
        sleep_duration: float = 0.0,
        disconnect_turn: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.sleep_duration = sleep_duration
        self.disconnect_turn = disconnect_turn
        self._has_slept = False

    def handle_message(self, env: Envelope) -> None:
        if env.type == MessageType.MOVE_REQUEST:
            state = env.payload.get("state", {})
            turn_number = state.get("turn_number", 0) + 1
            if self.disconnect_turn == turn_number:
                self.channel.close()
                return
            if self.sleep_duration > 0.0 and not self._has_slept:
                self._has_slept = True
                time.sleep(self.sleep_duration)
                return
        super().handle_message(env)


class FaultPlayerClient(PlayerClient):
    """Player client using FaultPlayerAgent to inject faults."""

    def __init__(
        self,
        *args: Any,
        sleep_duration: float = 0.0,
        disconnect_turn: int | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(*args, **kwargs)
        self.sleep_duration = sleep_duration
        self.disconnect_turn = disconnect_turn

    def start(self) -> None:
        self.client = TcpClient(
            self.host,
            self.port,
            self.connect_timeout,
            self.max_retries,
            self.backoff_base,
        )
        ch = self.client.connect()
        from agent_arena.shared.transport.channel import FramedChannel

        self.agent = FaultPlayerAgent(
            self.player_id,
            FramedChannel(ch),
            self.seed,
            sleep_duration=self.sleep_duration,
            disconnect_turn=self.disconnect_turn,
        )
        self.agent.run()


def test_integration_kill_player_mid_match() -> None:
    """RH2.3: kill a player mid-match → tagged forced verdict (disconnect)."""
    config = load_setup_config("config/setup.json")
    config.network.port = 0
    config.network.connect_timeout_seconds = 1.0
    config.network.read_timeout_seconds = 2.0
    config.game.move_timeout_seconds = 2.0

    ref_server = RefereeServer(config)
    ref_server.start()
    time.sleep(0.1)
    bound_port = ref_server.server.port

    c1 = FaultPlayerClient(
        "player_1", config.network.host, bound_port, 1.0, 42, 3, 0.05,
        disconnect_turn=3
    )
    c2 = FaultPlayerClient(
        "player_2", config.network.host, bound_port, 1.0, 42, 3, 0.05,
        disconnect_turn=3
    )

    t1 = threading.Thread(target=c1.start, daemon=True)
    t2 = threading.Thread(target=c2.start, daemon=True)
    t1.start()
    t2.start()

    t1.join(timeout=10.0)
    t2.join(timeout=10.0)
    if ref_server.game_thread:
        ref_server.game_thread.join(timeout=10.0)

    ref_server.stop()

    assert ref_server.final_state is not None
    assert ref_server.final_state.status == "COMPLETE"
    assert ref_server.final_state.verdict is not None
    assert ref_server.final_state.verdict.get("terminated_reason") == "disconnect"


def test_integration_timeout_turn() -> None:
    """RH2.3: timeout a turn → penalized skip."""
    config = load_setup_config("config/setup.json")
    config.network.port = 0
    config.network.connect_timeout_seconds = 1.0
    config.network.read_timeout_seconds = 2.0
    config.game.move_timeout_seconds = 0.5

    ref_server = RefereeServer(config)
    ref_server.start()
    time.sleep(0.1)
    bound_port = ref_server.server.port

    c1 = FaultPlayerClient(
        "player_1", config.network.host, bound_port, 1.0, 42, 3, 0.05,
        sleep_duration=1.0
    )
    c2 = FaultPlayerClient(
        "player_2", config.network.host, bound_port, 1.0, 42, 3, 0.05
    )

    t1 = threading.Thread(target=c1.start, daemon=True)
    t2 = threading.Thread(target=c2.start, daemon=True)
    t1.start()
    t2.start()

    t1.join(timeout=10.0)
    t2.join(timeout=10.0)
    if ref_server.game_thread:
        ref_server.game_thread.join(timeout=10.0)

    ref_server.stop()

    state = ref_server.final_state
    assert state is not None
    assert state.status == "COMPLETE"

    timeout_turns = [r for r in state.transcript if r.referee_flag == "timeout"]
    assert len(timeout_turns) >= 1
    assert timeout_turns[0].utterance == ""
    assert timeout_turns[0].word_count == 0
