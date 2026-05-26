"""Integration tests for the debate loop (RH2.1, RH2.2)."""
from __future__ import annotations

import json
import threading
import time

from agent_arena.services.game.debate_state import DebateState
from agent_arena.services.player.client import PlayerClient
from agent_arena.services.referee.server import RefereeServer
from agent_arena.shared.config import load_setup_config


def test_integration_full_lifecycle() -> None:
    """RH2.1: integration test — referee + 2 players on localhost, full lifecycle."""
    config = load_setup_config("config/setup.json")
    config.network.port = 0
    config.network.connect_timeout_seconds = 1.0
    config.network.read_timeout_seconds = 2.0
    config.game.move_timeout_seconds = 2.0

    ref_server = RefereeServer(config)
    ref_server.start()
    time.sleep(0.1)
    bound_port = ref_server.server.port

    def run_player(pid: str, seed: int) -> None:
        client = PlayerClient(
            player_id=pid,
            host=config.network.host,
            port=bound_port,
            connect_timeout=1.0,
            seed=seed,
            max_retries=3,
            backoff_base=0.05,
        )
        client.start()

    t1 = threading.Thread(target=run_player, args=("player_1", 42), daemon=True)
    t2 = threading.Thread(target=run_player, args=("player_2", 42), daemon=True)
    t1.start()
    t2.start()

    t1.join(timeout=10.0)
    t2.join(timeout=10.0)
    if ref_server.game_thread:
        ref_server.game_thread.join(timeout=10.0)

    ref_server.stop()

    assert ref_server.exception is None
    assert ref_server.final_state is not None
    assert ref_server.final_state.status == "COMPLETE"
    assert ref_server.final_state.verdict is not None
    assert "winner" in ref_server.final_state.verdict


def test_integration_determinism() -> None:
    """RH2.2: run same seed twice → assert byte-identical final_state.verdict."""
    def run_match(seed: int) -> DebateState | None:
        config = load_setup_config("config/setup.json")
        config.network.port = 0
        config.network.connect_timeout_seconds = 1.0
        config.network.read_timeout_seconds = 2.0
        config.game.move_timeout_seconds = 2.0
        config.debate.match.seed = seed

        ref_server = RefereeServer(config)
        ref_server.start()
        time.sleep(0.1)
        bound_port = ref_server.server.port

        def run_player(pid: str, p_seed: int) -> None:
            client = PlayerClient(
                player_id=pid,
                host=config.network.host,
                port=bound_port,
                connect_timeout=1.0,
                seed=p_seed,
                max_retries=3,
                backoff_base=0.05,
            )
            client.start()

        t1 = threading.Thread(target=run_player, args=("player_1", seed), daemon=True)
        t2 = threading.Thread(target=run_player, args=("player_2", seed), daemon=True)
        t1.start()
        t2.start()

        t1.join(timeout=10.0)
        t2.join(timeout=10.0)
        if ref_server.game_thread:
            ref_server.game_thread.join(timeout=10.0)

        ref_server.stop()
        return ref_server.final_state

    state1 = run_match(99)
    state2 = run_match(99)

    assert state1 is not None
    assert state2 is not None

    v1_bytes = json.dumps(state1.verdict, sort_keys=True).encode("utf-8")
    v2_bytes = json.dumps(state2.verdict, sort_keys=True).encode("utf-8")
    assert v1_bytes == v2_bytes
