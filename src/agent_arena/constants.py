# Immutable constants & default keys for agent-arena

# Versioning
EXPECTED_CONFIG_VERSION = "1.00"
PROTOCOL_VERSION = "1.00"

# Roles
ROLE_PLAYER_1 = "PLAYER_1"
ROLE_PLAYER_2 = "PLAYER_2"
ROLES = [ROLE_PLAYER_1, ROLE_PLAYER_2]

# Message type constants
MSG_REGISTER = "REGISTER"
MSG_REGISTER_ACK = "REGISTER_ACK"
MSG_ROLE_ASSIGN = "ROLE_ASSIGN"
MSG_GAME_START = "GAME_START"
MSG_MOVE_REQUEST = "MOVE_REQUEST"
MSG_MOVE_SUBMIT = "MOVE_SUBMIT"
MSG_STATE_UPDATE = "STATE_UPDATE"
MSG_GAME_OVER = "GAME_OVER"
MSG_ERROR = "ERROR"
MSG_HEARTBEAT = "HEARTBEAT"

# Network Defaults (used if config fails or fallback required)
DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 9000
DEFAULT_MAX_FRAME_SIZE = 10 * 1024 * 1024  # 10MB

# Debate error-code tokens (7.d, 8.4 — RG2.1)
ERROR_ILLEGAL_MOVE = "ILLEGAL_MOVE"
ERROR_MALFORMED_MESSAGE = "MALFORMED_MESSAGE"

# Debate move-flag / reason tokens (RG2.1)
FLAG_EMPTY = "empty"
FLAG_OVER_LENGTH = "over_length"
FLAG_MALFORMED = "malformed"
FLAG_CONCESSION = "concession"
FLAG_TIMEOUT = "timeout"
FLAG_RETRY_EXHAUSTED = "retry_exhausted"
FLAG_OFF_TOPIC = "off_topic"
FLAG_QUOTA_ABORTED = "quota_aborted"

# Terminated-reason tokens (8.3, 8.6 — RG2.2)
TERMINATED_DISCONNECT = "disconnect"
TERMINATED_ABORTED = "aborted"
TERMINATED_QUOTA_ABORTED = "quota_aborted"
