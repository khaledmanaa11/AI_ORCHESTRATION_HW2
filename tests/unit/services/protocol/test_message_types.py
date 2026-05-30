"""Unit tests for agent_arena.services.protocol.message_types."""
import pytest

from agent_arena.services.protocol.message_types import ErrorCode, MessageType

_EXPECTED = {
    "REGISTER": "register",
    "REGISTER_ACK": "register_ack",
    "ROLE_ASSIGN": "role_assign",
    "GAME_START": "game_start",
    "MOVE_REQUEST": "move_request",
    "MOVE_SUBMIT": "move_submit",
    "STATE_UPDATE": "state_update",
    "GAME_OVER": "game_over",
    "ERROR": "error",
    "HEARTBEAT": "heartbeat",
}

# Wire values are frozen (protocol v1.00). MALFORMED_MESSAGE in particular must stay
# UPPERCASE because the game loop already emits that exact string on the wire.
_EXPECTED_ERROR_CODES = {
    "VERSION_MISMATCH": "VERSION_MISMATCH",
    "MALFORMED_MESSAGE": "MALFORMED_MESSAGE",
    "UNKNOWN_TYPE": "UNKNOWN_TYPE",
    "UNEXPECTED_MESSAGE": "UNEXPECTED_MESSAGE",
}


def test_all_members_present_with_expected_values():
    assert {m.name: m.value for m in MessageType} == _EXPECTED


def test_error_codes_frozen_wire_values():
    assert {m.name: m.value for m in ErrorCode} == _EXPECTED_ERROR_CODES


def test_value_lookup():
    assert MessageType("register") == MessageType.REGISTER
    assert MessageType("game_start") == MessageType.GAME_START


def test_unknown_value_raises():
    with pytest.raises(ValueError):
        MessageType("banana")
