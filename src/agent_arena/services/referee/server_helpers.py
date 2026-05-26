"""Small helpers for RefereeServer wiring."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from agent_arena.constants import PROTOCOL_VERSION
from agent_arena.services.game.debate_engine import DebateEngine
from agent_arena.services.protocol.codec import encode
from agent_arena.services.protocol.envelope import Envelope
from agent_arena.services.protocol.message_types import MessageType
from agent_arena.shared.config import SetupConfig
from agent_arena.shared.transport.channel import Channel


def send_referee_message(
    channel: Channel,
    match_id: str | None,
    message_type: MessageType,
    payload: dict[str, Any],
    seq: int,
) -> None:
    """Encode and send one referee-authored envelope."""
    env = Envelope(
        protocol_version=PROTOCOL_VERSION,
        type=message_type,
        match_id=match_id,
        sender="referee",
        seq=seq,
        timestamp=datetime.now(timezone.utc).isoformat(),
        payload=payload,
    )
    channel.send(encode(env))


def load_evidence_pack(pack_id: str) -> dict[str, Any]:
    """Load the configured pack from data/ or config/fixtures/."""
    evidence_pack: dict[str, Any] = {"pack_id": pack_id}
    for folder in (Path("data"), Path("config/fixtures")):
        file_path = folder / f"{pack_id}.json"
        if not file_path.exists():
            continue
        try:
            with file_path.open("r", encoding="utf-8") as f:
                evidence_pack = json.load(f)
                evidence_pack.setdefault("pack_id", pack_id)
        except Exception:
            return {"pack_id": pack_id}
        break
    return evidence_pack


def build_debate_engine(config: SetupConfig) -> DebateEngine:
    """Create a DebateEngine from validated config."""
    return DebateEngine(
        {
            "r": config.debate.format.rebuttal_rounds,
            "word_cap": config.debate.format.word_cap,
            "retry_cap": config.debate.format.retry_cap,
            "first_speaker": config.debate.format.first_speaker,
            "motion": config.debate.match.motion,
        }
    )
