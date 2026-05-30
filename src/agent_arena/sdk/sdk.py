from __future__ import annotations

import threading
from typing import TYPE_CHECKING

from agent_arena.apps.run_helpers import (
    build_referee_brain,
    print_transcript,
)
from agent_arena.services.player.client import PlayerClient
from agent_arena.services.referee.server import RefereeServer
from agent_arena.shared.api_gatekeeper import APIGatekeeper
from agent_arena.shared.llm_client import LLMClient
from agent_arena.shared.shutdown import ShutdownCoordinator

if TYPE_CHECKING:
    from agent_arena.shared.config import SetupConfig


class ArenaSDK:
    """Single entry point for all logic in the agent-arena application."""

    @classmethod
    def start_referee(
        cls,
        config: SetupConfig,
        brain_choice: str = "simple",
        move_timeout: float | None = None,
        show_transcript: bool = False,
    ) -> None:
        """Construct and run the referee server matching the referee_app logic."""
        if move_timeout is not None:
            config.game.move_timeout_seconds = move_timeout
        gatekeeper = APIGatekeeper(**config.llm.gatekeeper.model_dump())
        brain = build_referee_brain(config, brain_choice)
        brain.api_gatekeeper = gatekeeper
        if brain_choice == "llm":
            brain._client = LLMClient(provider=config.llm.provider, gatekeeper=gatekeeper)
        coordinator = ShutdownCoordinator()
        coordinator.install_signal_handlers()
        server = RefereeServer(config, brain=brain, coordinator=coordinator)

        try:
            server.start()
            print(f"Referee listening on {config.network.host}:{server.server.port}")
            print("Waiting for two players...")
            coordinator.wait()
            if server.game_thread is not None:
                server.game_thread.join()
            if server.exception is not None:
                raise server.exception
            if show_transcript:
                print_transcript(server.final_state)
        finally:
            server.stop()

    @classmethod
    def start_player(
        cls,
        config: SetupConfig,
        player_id: str,
        brain_choice: str = "config",
        seed: int | None = None,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        """Construct and run the player client matching the player_app logic."""
        if brain_choice != "config":
            config.debate.player.brain_choice = brain_choice
        gatekeeper = APIGatekeeper(**config.llm.gatekeeper.model_dump())
        object.__setattr__(config, "api_gatekeeper", gatekeeper)

        actual_seed = seed if seed is not None else config.debate.match.seed
        actual_host = host or config.network.host
        actual_port = port if port is not None else config.network.port
        coordinator = ShutdownCoordinator()
        coordinator.install_signal_handlers()
        client = PlayerClient(
            player_id=player_id,
            host=actual_host,
            port=actual_port,
            connect_timeout=config.network.connect_timeout_seconds,
            seed=actual_seed,
            config=config,
            coordinator=coordinator,
        )
        print(f"Player {player_id} connecting to {actual_host}:{actual_port} with {config.debate.player.brain_choice} brain")
        exceptions: list[Exception] = []

        def _run_client() -> None:
            try:
                client.start()
            except Exception as exc:
                exceptions.append(exc)
                coordinator.request_shutdown("player_client_exception")

        client_thread = threading.Thread(target=_run_client, daemon=True, name="player-client")
        try:
            client_thread.start()
            coordinator.wait()
            client_thread.join()
            if exceptions:
                raise exceptions[0]
        finally:
            client.close()
        print(f"Player {player_id} finished")
