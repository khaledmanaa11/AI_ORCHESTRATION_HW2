"""Shared CLI helpers for running visible debate matches."""
from __future__ import annotations

import sys
import time
from typing import TextIO

from agent_arena.services.game.debate_state import DebateState
from agent_arena.services.referee.brain.llm_brain import LLMRefereeBrain
from agent_arena.services.referee.brain.simple_brain import SimpleRefereeBrain
from agent_arena.services.referee.server import RefereeServer
from agent_arena.shared.config import SetupConfig


def build_referee_brain(config: SetupConfig, choice: str):
    """Build the configured referee brain for CLI entry points."""
    if choice == "llm":
        return LLMRefereeBrain(model_name=config.llm.model_name, provider=config.llm.provider)
    return SimpleRefereeBrain()


def wait_for_match(server: RefereeServer, poll_seconds: float = 0.2) -> DebateState | None:
    """Wait until the server has run one complete match."""
    while server.game_thread is None:
        if server.exception is not None:
            raise server.exception
        time.sleep(poll_seconds)
    server.game_thread.join()
    if server.exception is not None:
        raise server.exception
    return server.final_state


def print_transcript(state: DebateState | None, stream: TextIO | None = None) -> None:
    """Print a readable debate transcript and verdict."""
    out = stream or sys.stdout
    if state is None:
        print("No final state was produced.", file=out)
        return

    print("\n=== Debate Transcript ===", file=out)
    print(f"Motion: {state.motion}", file=out)
    for turn in state.transcript:
        print(
            f"\nTurn {turn.turn_number:02d} | {turn.side} | "
            f"{turn.phase} | {turn.word_count} words",
            file=out,
        )
        print(turn.utterance.strip(), file=out)
        if turn.referee_tell:
            print(f"[referee tell] {turn.referee_tell}", file=out)
        if turn.referee_flag:
            print(f"[referee flag] {turn.referee_flag}", file=out)

    verdict = state.verdict or {}
    print("\n=== Verdict ===", file=out)
    print(f"Winner: {verdict.get('winner', 'unknown')}", file=out)
    if "margin" in verdict:
        print(f"Margin: {verdict['margin']}", file=out)
    rationale = verdict.get("rationale")
    if rationale:
        print(f"Rationale: {rationale}", file=out)
