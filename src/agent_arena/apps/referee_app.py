"""Console entry point for the referee process."""
from __future__ import annotations

import argparse
import logging

from agent_arena.sdk.sdk import ArenaSDK
from agent_arena.shared.config import load_setup_config


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
    ArenaSDK.start_referee(
        config=config,
        brain_choice=args.brain,
        move_timeout=args.move_timeout,
        show_transcript=args.show_transcript,
    )


if __name__ == "__main__":
    main()
