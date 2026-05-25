"""Unit tests for agent_arena.services.protocol.codec."""
import json

import pytest

from agent_arena.services.protocol.codec import CodecError, decode, encode
from agent_arena.services.protocol.envelope import Envelope
from agent_arena.services.protocol.message_types import MessageType


def _make(msg_type: MessageType) -> Envelope:
    return Envelope(
        protocol_version="1.00",
        type=msg_type,
        match_id=None if msg_type is MessageType.REGISTER else "m-1",
        sender="player-a",
        seq=3,
        timestamp="2026-05-25T00:00:00Z",
        payload={"k": "v"},
    )


@pytest.mark.parametrize("msg_type", list(MessageType))
def test_round_trip_all_types(msg_type):
    env = _make(msg_type)
    assert decode(encode(env)) == env


def test_type_serialized_as_string_value():
    env = _make(MessageType.GAME_START)
    assert json.loads(encode(env))["type"] == "game_start"


def test_encode_output_is_valid_json():
    env = _make(MessageType.HEARTBEAT)
    assert json.loads(encode(env))  # does not raise


def test_decode_malformed_json_raises():
    with pytest.raises(CodecError):
        decode(b"not json")


def test_decode_missing_field_raises():
    with pytest.raises(CodecError):
        decode(b'{"type": "register"}')


def test_decode_unknown_type_raises():
    obj = {
        "protocol_version": "1.00",
        "type": "banana",
        "match_id": "m-1",
        "sender": "p",
        "seq": 0,
        "timestamp": "t",
        "payload": {},
    }
    with pytest.raises(CodecError):
        decode(json.dumps(obj).encode("utf-8"))
