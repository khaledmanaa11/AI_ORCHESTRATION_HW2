"""Shared CLI helpers for running visible debate matches."""
from __future__ import annotations

import sys
import time
from collections.abc import Mapping
from typing import TextIO

from agent_arena.constants import FLAG_QUOTA_ABORTED, TERMINATED_QUOTA_ABORTED
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


_DEFAULT_FLAGS = ("timeout", "retry_exhausted", "disconnect")


def _format_api_value(value: object) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, float):
        return f"{value:.2f}".rstrip("0").rstrip(".")
    return str(value)


def _rpd_used(api_state: Mapping[str, object]) -> object:
    explicit = api_state.get("rpd_used")
    if explicit is not None:
        return explicit

    limit = api_state.get("rpd_limit", api_state.get("rpd"))
    remaining = api_state.get("rpd_remaining")
    if isinstance(limit, (int, float)) and isinstance(remaining, (int, float)):
        return max(0, limit - remaining)
    return None


def _default_summary(state: DebateState) -> dict[str, int]:
    """Count per-side defaulted turns (timeout / retry_exhausted / disconnect)."""
    counts: dict[str, int] = {"PRO": 0, "CON": 0}
    for turn in state.transcript:
        if turn.referee_flag in _DEFAULT_FLAGS:
            counts[turn.side] = counts.get(turn.side, 0) + 1
    return counts


def _has_quota_aborted(state: DebateState, verdict: dict) -> bool:
    if verdict.get("terminated_reason") == TERMINATED_QUOTA_ABORTED:
        return True
    return any(turn.referee_flag == FLAG_QUOTA_ABORTED for turn in state.transcript)


def _print_quota_aborted_banner(out: TextIO) -> None:
    print("\n!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", file=out)
    print(
        "WARNING: this match was terminated by API capacity exhaustion - "
        "not a real forfeit",
        file=out,
    )
    print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", file=out)


def _print_api_gatekeeper(api_state: Mapping[str, object], out: TextIO) -> None:
    print("\n=== API Gatekeeper ===", file=out)
    print(
        "RPD used/remaining: "
        f"{_format_api_value(_rpd_used(api_state))} / "
        f"{_format_api_value(api_state.get('rpd_remaining'))}",
        file=out,
    )
    print(f"RPD resets at: {_format_api_value(api_state.get('rpd_resets_at'))}", file=out)
    print(f"RPM tokens: {_format_api_value(api_state.get('rpm_tokens'))}", file=out)
    print(
        "In flight: "
        f"{_format_api_value(api_state.get('in_flight'))} / "
        f"{_format_api_value(api_state.get('max_concurrency'))}",
        file=out,
    )
    print(f"Breaker state: {_format_api_value(api_state.get('breaker_state'))}", file=out)
    print(
        "Consecutive failures: "
        f"{_format_api_value(api_state.get('consecutive_failures'))}",
        file=out,
    )
    opened_at = api_state.get("breaker_opened_at")
    if opened_at:
        print(f"Breaker opened at: {opened_at}", file=out)


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

    defaults = _default_summary(state)
    total_defaults = defaults["PRO"] + defaults["CON"]
    verdict = state.verdict or {}
    winner = verdict.get("winner", "unknown")
    if _has_quota_aborted(state, verdict):
        _print_quota_aborted_banner(out)

    print("\n=== Verdict ===", file=out)
    print(f"Winner: {winner}", file=out)
    if "margin" in verdict:
        print(f"Margin: {verdict['margin']}", file=out)
    rationale = verdict.get("rationale")
    if rationale:
        print(f"Rationale: {rationale}", file=out)
    if "terminated_reason" in verdict:
        print(f"Terminated: {verdict['terminated_reason']}", file=out)

    api_state = verdict.get("api_state")
    if isinstance(api_state, Mapping):
        _print_api_gatekeeper(api_state, out)

    if total_defaults > 0:
        print(
            f"\n[!] Forfeited turns — PRO: {defaults['PRO']}, CON: {defaults['CON']}. "
            "Verdict reflects a partial debate; treat margin with caution.",
            file=out,
        )
        loser = "CON" if winner == "PRO" else "PRO" if winner == "CON" else None
        if loser and defaults[loser] > defaults.get(winner, 0):
            print(
                f"[!] Losing side ({loser}) defaulted more turns than the winner — "
                "the result is likely a forfeit, not a genuine outcome.",
                file=out,
            )
