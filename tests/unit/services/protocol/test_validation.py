"""Unit tests for agent_arena.services.protocol.validation."""
import pytest

from agent_arena.services.protocol.envelope import Envelope
from agent_arena.services.protocol.message_types import MessageType
from agent_arena.services.protocol.validation import (
    ProtocolVersionError,
    ValidationError,
    validate,
)

_VERSION = "1.00"


def _env(
    *,
    msg_type: MessageType,
    match_id: str | None,
    version: str = _VERSION,
    seq: int = 0,
) -> Envelope:
    return Envelope(
        protocol_version=version,
        type=msg_type,
        match_id=match_id,
        sender="player-a",
        seq=seq,
        timestamp="2026-05-25T00:00:00Z",
        payload={},
    )


def test_valid_register_passes():
    validate(_env(msg_type=MessageType.REGISTER, match_id=None), _VERSION)


def test_valid_non_register_passes():
    validate(_env(msg_type=MessageType.GAME_START, match_id="m-1"), _VERSION)


def test_wrong_version_raises():
    env = _env(msg_type=MessageType.REGISTER, match_id=None, version="0.90")
    with pytest.raises(ProtocolVersionError):
        validate(env, _VERSION)


def test_none_match_id_on_non_register_raises():
    env = _env(msg_type=MessageType.GAME_START, match_id=None)
    with pytest.raises(ValidationError):
        validate(env, _VERSION)


def test_negative_seq_raises():
    env = _env(msg_type=MessageType.GAME_START, match_id="m-1", seq=-1)
    with pytest.raises(ValidationError):
        validate(env, _VERSION)


def test_register_with_none_match_id_and_correct_version_passes():
    validate(_env(msg_type=MessageType.REGISTER, match_id=None), _VERSION)
