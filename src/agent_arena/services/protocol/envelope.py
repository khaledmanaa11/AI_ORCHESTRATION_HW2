from dataclasses import dataclass

from agent_arena.services.protocol.message_types import MessageType


@dataclass(frozen=True)
class Envelope:
    """Immutable wrapper carrying routing/sequencing metadata around every message payload."""

    protocol_version: str
    type: MessageType
    match_id: str | None
    sender: str
    seq: int
    timestamp: str
    payload: dict
