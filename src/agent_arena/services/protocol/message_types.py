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
