"""Unit tests for agent_arena.shared.transport.framing."""
import struct

import pytest

from agent_arena.shared.transport.channel import Channel, ConnectionClosedError, InMemoryChannel
from agent_arena.shared.transport.framing import (
    FrameTooLargeError,
    recv_frame,
    send_frame,
)

_MAX = 1_000_000


class _ScriptedChannel(Channel):
    """Channel that hands back a predefined list of byte chunks, one per recv()."""

    def __init__(self, chunks: list[bytes]) -> None:
        self._chunks = list(chunks)

    def send(self, data: bytes) -> None:  # noqa: ARG002
        raise NotImplementedError

    def recv(self) -> bytes:
        if not self._chunks:
            return b""
        return self._chunks.pop(0)


def test_round_trip():
    a, b = InMemoryChannel.make_pair()
    payload = b"arbitrary \x00\x01\x02 bytes"
    send_frame(a, payload)
    assert recv_frame(b, _MAX) == payload


def test_empty_payload():
    a, b = InMemoryChannel.make_pair()
    send_frame(a, b"")
    assert recv_frame(b, _MAX) == b""


def test_oversized_frame_raises():
    ch = _ScriptedChannel([struct.pack(">I", 11)])
    with pytest.raises(FrameTooLargeError):
        recv_frame(ch, max_bytes=10)


def test_oversized_frame_does_not_read_payload():
    # Only the header is provided; if recv_frame tried to read the payload it would
    # hit b"" and raise ConnectionClosedError instead of FrameTooLargeError.
    ch = _ScriptedChannel([struct.pack(">I", 11)])
    with pytest.raises(FrameTooLargeError):
        recv_frame(ch, max_bytes=10)


def test_split_payload_one_byte_at_a_time():
    payload = b"hello world"
    framed = struct.pack(">I", len(payload)) + payload
    ch = _ScriptedChannel([framed[i : i + 1] for i in range(len(framed))])
    assert recv_frame(ch, _MAX) == payload


def test_close_during_header_read():
    ch = _ScriptedChannel([b"\x00\x00"])  # only 2 of 4 header bytes, then b""
    with pytest.raises(ConnectionClosedError):
        recv_frame(ch, _MAX)


def test_close_during_payload_read():
    header = struct.pack(">I", 100)
    ch = _ScriptedChannel([header, b"x" * 50])  # declares 100, delivers 50, then b""
    with pytest.raises(ConnectionClosedError):
        recv_frame(ch, _MAX)
