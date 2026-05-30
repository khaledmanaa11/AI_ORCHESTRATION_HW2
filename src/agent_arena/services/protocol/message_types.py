from enum import Enum


class MessageType(str, Enum):
    """Authoritative set of every message type in the match lifecycle."""

    REGISTER = "register"
    REGISTER_ACK = "register_ack"
    ROLE_ASSIGN = "role_assign"
    GAME_START = "game_start"
    MOVE_REQUEST = "move_request"
    MOVE_SUBMIT = "move_submit"
    STATE_UPDATE = "state_update"
    GAME_OVER = "game_over"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class ErrorCode(str, Enum):
    """Authoritative set of error codes sent in ERROR messages.

    Values are UPPERCASE to preserve the existing wire format (the referee already
    emits ``"MALFORMED_MESSAGE"`` in the game loop); the protocol is frozen at v1.00.
    """

    VERSION_MISMATCH = "VERSION_MISMATCH"
    MALFORMED_MESSAGE = "MALFORMED_MESSAGE"
    UNKNOWN_TYPE = "UNKNOWN_TYPE"
    UNEXPECTED_MESSAGE = "UNEXPECTED_MESSAGE"
