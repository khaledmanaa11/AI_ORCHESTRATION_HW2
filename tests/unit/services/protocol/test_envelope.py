"""Unit tests for agent_arena.services.protocol.envelope."""
import dataclasses

import pytest

from agent_arena.services.protocol.envelope import Envelope
from agent_arena.services.protocol.message_types import MessageType


def _make(match_id: str | None) -> Envelope:
    return Envelope(
        protocol_version="1.00",
        type=MessageType.REGISTER if match_id is None else MessageType.GAME_START,
        match_id=match_id,
        sender="player-a",
        seq=0,
        timestamp="2026-05-25T00:00:00Z",
        payload={},
    )


def test_construct_with_none_match_id():
    env = _make(None)
    assert env.match_id is None


def test_construct_with_string_match_id():
    env = _make("m-123")
    assert env.match_id == "m-123"


def test_frozen():
    env = _make("m-123")
    with pytest.raises(dataclasses.FrozenInstanceError):
        env.sender = "x"
