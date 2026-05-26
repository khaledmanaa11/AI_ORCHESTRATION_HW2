"""Output parser for player brain responses (Module P3, BS-1)."""
from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ParsedTurn:
    """Structured response from a player brain turn (RP3.1)."""

    read_profile: dict[str, Any]
    reflexion_lesson: str
    candidate_drafts: list[dict[str, Any]]


def parse(raw: str) -> ParsedTurn:
    """Parse raw LLM output into a ParsedTurn with defensive fallbacks (RP3.1-3.3)."""
    fallback_turn = ParsedTurn(
        read_profile={},
        reflexion_lesson="",
        candidate_drafts=[{"text": raw, "targets": []}],
    )

    if not raw:
        return fallback_turn

    try:
        raw_stripped = raw.strip()
        # Strip markdown JSON fences if present
        if raw_stripped.startswith("```"):
            lines = raw_stripped.splitlines()
            if len(lines) >= 2 and lines[-1].startswith("```"):
                # Strip the first line (e.g. ```json) and the last line (```)
                raw_stripped = "\n".join(lines[1:-1]).strip()

        # Parse JSON
        try:
            data = json.loads(raw_stripped)
        except json.JSONDecodeError:
            # Fallback attempt: find content between first '{' and last '}'
            start = raw_stripped.find("{")
            end = raw_stripped.rfind("}")
            if start != -1 and end != -1 and end > start:
                data = json.loads(raw_stripped[start : end + 1])
            else:
                return fallback_turn

        if not isinstance(data, dict):
            return fallback_turn

        # Process read_profile
        read_profile = data.get("read_profile")
        if not isinstance(read_profile, dict):
            read_profile = {}

        # Process reflexion_lesson
        reflexion_lesson = data.get("reflexion_lesson")
        if not isinstance(reflexion_lesson, str):
            reflexion_lesson = ""

        # Process candidate_drafts
        candidate_drafts_raw = data.get("candidate_drafts")
        if not isinstance(candidate_drafts_raw, list):
            return fallback_turn

        candidate_drafts: list[dict[str, Any]] = []
        for draft in candidate_drafts_raw:
            if isinstance(draft, dict):
                text = draft.get("text")
                if not isinstance(text, str):
                    text = str(text) if text is not None else ""
                targets_raw = draft.get("targets")
                targets = [str(t) for t in targets_raw] if isinstance(targets_raw, list) else []
                candidate_drafts.append({"text": text, "targets": targets})
            elif isinstance(draft, str):
                candidate_drafts.append({"text": draft, "targets": []})

        if not candidate_drafts:
            return fallback_turn

        return ParsedTurn(
            read_profile=read_profile,
            reflexion_lesson=reflexion_lesson,
            candidate_drafts=candidate_drafts,
        )

    except Exception:
        return fallback_turn
