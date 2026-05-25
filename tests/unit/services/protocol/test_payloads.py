"""Unit tests for agent_arena.services.protocol.payloads."""
import dataclasses

import pytest

from agent_arena.services.protocol import payloads as p


def test_register_payload():
    assert p.RegisterPayload("a1", "Alice", "1.00").agent_id == "a1"


def test_register_ack_payload():
    assert p.RegisterAckPayload(True, "m1", None).accepted is True


def test_role_assign_payload():
    assert p.RoleAssignPayload("attacker", {"k": 1}).role == "attacker"


def test_game_start_payload():
    assert p.GameStartPayload({"board": []}, ["a", "b"]).turn_order == ["a", "b"]


def test_move_request_payload():
    assert p.MoveRequestPayload({}, [], 5.0).move_timeout_seconds == 5.0


def test_move_submit_payload():
    assert p.MoveSubmitPayload({"x": 1}).move == {"x": 1}


def test_state_update_payload():
    assert p.StateUpdatePayload({}, {}, "a").active_player == "a"


def test_game_over_payload():
    assert p.GameOverPayload("win", "checkmate", {}).result == "win"


def test_error_payload():
    assert p.ErrorPayload("E1", "boom").code == "E1"


def test_heartbeat_payload_no_required_fields():
    assert p.HeartbeatPayload() is not None


@pytest.mark.parametrize(
    "instance",
    [
        p.RegisterPayload("a1", "Alice", "1.00"),
        p.MoveSubmitPayload({"x": 1}),
        p.HeartbeatPayload(),
    ],
)
def test_payloads_are_frozen(instance):
    with pytest.raises(dataclasses.FrozenInstanceError):
        instance.foo = "bar"
