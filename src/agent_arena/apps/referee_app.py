"""Console entry point for the referee process."""
from __future__ import annotations

import argparse
import logging

from agent_arena.apps.run_helpers import (
    build_referee_brain,
    print_transcript,
    wait_for_match,
)
from agent_arena.services.referee.server import RefereeServer
from agent_arena.shared.api_gatekeeper import APIGatekeeper
from agent_arena.shared.config import load_setup_config
from agent_arena.shared.llm_client import LLMClient


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the Agent Arena referee.")
    parser.add_argument("--config", default="config/setup.json")
    parser.add_argument("--brain", choices=["simple", "llm"], default="simple")
    parser.add_argument("--move-timeout", type=float, default=None)
    parser.add_argument("--show-transcript", action="store_true")
    parser.add_argument("--log-level", default="INFO")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    logging.basicConfig(
        level=getattr(logging, args.log_level.upper(), logging.INFO),
        format="%(levelname)s:%(name)s:%(message)s",
    )
    config = load_setup_config(args.config)
    if args.move_timeout is not None:
        config.game.move_timeout_seconds = args.move_timeout
    gatekeeper = APIGatekeeper(**config.llm.gatekeeper.model_dump())
    brain = build_referee_brain(config, args.brain)
    brain.api_gatekeeper = gatekeeper
    if args.brain == "llm":
        brain._client = LLMClient(provider=config.llm.provider, gatekeeper=gatekeeper)
    server = RefereeServer(config, brain=brain)

    try:
        server.start()
        print(f"Referee listening on {config.network.host}:{server.server.port}")
        print("Waiting for two players...")
        state = wait_for_match(server)
        if args.show_transcript:
            print_transcript(state)
    finally:
        server.stop()


if __name__ == "__main__":
    main()
