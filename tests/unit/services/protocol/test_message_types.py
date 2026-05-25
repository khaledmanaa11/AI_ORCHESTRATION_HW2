"""Unit tests for agent_arena.services.protocol.message_types."""
import pytest

from agent_arena.services.protocol.message_types import MessageType

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


def test_all_members_present_with_expected_values():
    assert {m.name: m.value for m in MessageType} == _EXPECTED


def test_value_lookup():
    assert MessageType("register") == MessageType.REGISTER
    assert MessageType("game_start") == MessageType.GAME_START


def test_unknown_value_raises():
    with pytest.raises(ValueError):
        MessageType("banana")
