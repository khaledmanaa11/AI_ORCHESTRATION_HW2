from agent_arena.services.protocol.envelope import Envelope
from agent_arena.services.protocol.message_types import MessageType


class ProtocolVersionError(ValueError):
    """Raised when an envelope's protocol_version does not match the expected one."""


class UnknownMessageTypeError(ValueError):
    """Raised when an envelope's type is not a valid MessageType member."""


class ValidationError(ValueError):
    """Raised when an envelope violates a structural contract."""


def validate(envelope: Envelope, expected_version: str) -> None:
    if envelope.protocol_version != expected_version:
        raise ProtocolVersionError(
            f"expected protocol version {expected_version!r}, "
            f"got {envelope.protocol_version!r}"
        )
    if not isinstance(envelope.type, MessageType):
        raise UnknownMessageTypeError(f"unknown message type: {envelope.type!r}")
    if envelope.match_id is None and envelope.type != MessageType.REGISTER:
        raise ValidationError(
            f"match_id may only be None on REGISTER, not {envelope.type.value}"
        )
    if not isinstance(envelope.seq, int) or envelope.seq < 0:
        raise ValidationError(f"seq must be a non-negative integer, got {envelope.seq!r}")
