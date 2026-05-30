"""Console entry point for a player process."""
from __future__ import annotations

import argparse
import logging
import threading

from agent_arena.services.player.client import PlayerClient
from agent_arena.shared.api_gatekeeper import APIGatekeeper
from agent_arena.shared.config import load_setup_config
from agent_arena.shared.shutdown import ShutdownCoordinator


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run an Agent Arena player.")
    parser.add_argument("--config", default="config/setup.json")
    parser.add_argument("--name", required=True)
    parser.add_argument("--brain", choices=["config", "seeded", "llm"], default="config")
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--host", default=None)
    parser.add_argument("--port", type=int, default=None)
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s:%(name)s:%(message)s",
    )
    config = load_setup_config(args.config)
    if args.brain != "config":
        config.debate.player.brain_choice = args.brain
    gatekeeper = APIGatekeeper(**config.llm.gatekeeper.model_dump())
    object.__setattr__(config, "api_gatekeeper", gatekeeper)

    seed = args.seed if args.seed is not None else config.debate.match.seed
    host = args.host or config.network.host
    port = args.port if args.port is not None else config.network.port
    coordinator = ShutdownCoordinator()
    coordinator.install_signal_handlers()
    client = PlayerClient(
        player_id=args.name,
        host=host,
        port=port,
        connect_timeout=config.network.connect_timeout_seconds,
        seed=seed,
        config=config,
        coordinator=coordinator,
    )
    print(f"Player {args.name} connecting to {host}:{port} with {config.debate.player.brain_choice} brain")
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
    print(f"Player {args.name} finished")


if __name__ == "__main__":
    main()
