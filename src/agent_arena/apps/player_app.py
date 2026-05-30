"""Console entry point for a player process."""
from __future__ import annotations

import argparse
import logging

from agent_arena.sdk.sdk import ArenaSDK
from agent_arena.shared.config import load_setup_config


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
    ArenaSDK.start_player(
        config=config,
        player_id=args.name,
        brain_choice=args.brain,
        seed=args.seed,
        host=args.host,
        port=args.port,
    )


if __name__ == "__main__":
    main()
