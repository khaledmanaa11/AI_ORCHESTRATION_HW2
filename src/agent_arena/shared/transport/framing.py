import struct

from agent_arena.shared.transport.channel import Channel, ConnectionClosedError

_HEADER_FORMAT = ">I"
_HEADER_SIZE = 4


class FrameTooLargeError(IOError):
    """Raised when a frame header declares a payload larger than the allowed maximum."""


def send_frame(channel: Channel, data: bytes) -> None:
    header = struct.pack(_HEADER_FORMAT, len(data))
    channel.send(header + data)


def _fill(channel: Channel, buffer: bytearray, target: int) -> None:
    while len(buffer) < target:
        chunk = channel.recv()
        if not chunk:
            raise ConnectionClosedError("peer closed connection mid-frame")
        buffer.extend(chunk)


def recv_frame(channel: Channel, max_bytes: int) -> bytes:
    buffer = bytearray()
    _fill(channel, buffer, _HEADER_SIZE)
    (payload_length,) = struct.unpack(_HEADER_FORMAT, bytes(buffer[:_HEADER_SIZE]))
    if payload_length > max_bytes:
        raise FrameTooLargeError(
            f"frame declares {payload_length} bytes; max is {max_bytes}"
        )
    total = _HEADER_SIZE + payload_length
    _fill(channel, buffer, total)
    return bytes(buffer[_HEADER_SIZE:total])
