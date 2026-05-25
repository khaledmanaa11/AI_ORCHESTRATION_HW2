from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RegisterPayload:
    agent_id: str
    agent_name: str
    protocol_version: str


@dataclass(frozen=True)
class RegisterAckPayload:
    accepted: bool
    match_id: str | None
    reason: str | None


@dataclass(frozen=True)
class RoleAssignPayload:
    role: str
    game_config: dict[str, Any]


@dataclass(frozen=True)
class GameStartPayload:
    initial_state: dict[str, Any]
    turn_order: list[str]


@dataclass(frozen=True)
class MoveRequestPayload:
    state: dict[str, Any]
    legal_moves: list[Any]
    move_timeout_seconds: float


@dataclass(frozen=True)
class MoveSubmitPayload:
    move: dict[str, Any]


@dataclass(frozen=True)
class StateUpdatePayload:
    state: dict[str, Any]
    last_move: dict[str, Any]
    active_player: str


@dataclass(frozen=True)
class GameOverPayload:
    result: str
    reason: str
    final_state: dict[str, Any]


@dataclass(frozen=True)
class ErrorPayload:
    code: str
    message: str


@dataclass(frozen=True)
class HeartbeatPayload:
    """Empty — a heartbeat carries no data beyond its envelope."""
