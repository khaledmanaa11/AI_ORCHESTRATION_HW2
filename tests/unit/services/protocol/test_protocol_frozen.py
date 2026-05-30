"""Unit tests ensuring the protocol version and message types remain frozen."""
from agent_arena.constants import PROTOCOL_VERSION
from agent_arena.services.protocol.message_types import MessageType


def test_protocol_version_is_frozen():
    """Assert that the PROTOCOL_VERSION is frozen at '1.00'."""
    assert PROTOCOL_VERSION == "1.00"


def test_message_types_are_frozen():
    """Assert that the MessageType enum members are frozen and no new ones are added."""
    expected_members = {
        "REGISTER",
        "REGISTER_ACK",
        "ROLE_ASSIGN",
        "GAME_START",
        "MOVE_REQUEST",
        "MOVE_SUBMIT",
        "STATE_UPDATE",
        "GAME_OVER",
        "ERROR",
        "HEARTBEAT",
    }
    current_members = {m.name for m in MessageType}
    assert current_members == expected_members
