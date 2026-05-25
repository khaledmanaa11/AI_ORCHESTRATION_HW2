import json

from agent_arena.services.protocol.envelope import Envelope
from agent_arena.services.protocol.message_types import MessageType

_REQUIRED_FIELDS = (
    "protocol_version",
    "type",
    "match_id",
    "sender",
    "seq",
    "timestamp",
    "payload",
)


class CodecError(ValueError):
    """Raised when bytes cannot be decoded into a well-formed Envelope."""


def encode(envelope: Envelope) -> bytes:
    obj = {
        "protocol_version": envelope.protocol_version,
        "type": envelope.type.value,
        "match_id": envelope.match_id,
        "sender": envelope.sender,
        "seq": envelope.seq,
        "timestamp": envelope.timestamp,
        "payload": envelope.payload,
    }
    return json.dumps(obj).encode("utf-8")


def decode(data: bytes) -> Envelope:
    try:
        obj = json.loads(data)
    except json.JSONDecodeError as exc:
        raise CodecError(f"malformed JSON: {exc}") from exc
    try:
        fields = {key: obj[key] for key in _REQUIRED_FIELDS}
    except KeyError as exc:
        raise CodecError(f"missing required field: {exc}") from exc
    try:
        msg_type = MessageType(fields["type"])
    except ValueError as exc:
        raise CodecError(f"unknown message type: {fields['type']!r}") from exc
    return Envelope(
        protocol_version=fields["protocol_version"],
        type=msg_type,
        match_id=fields["match_id"],
        sender=fields["sender"],
        seq=fields["seq"],
        timestamp=fields["timestamp"],
        payload=fields["payload"],
    )
