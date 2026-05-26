import queue
from abc import ABC, abstractmethod


class ConnectionClosedError(IOError):
    """Raised when the peer has closed the connection."""


class Channel(ABC):
    """Abstract transport interface. Domain services never touch sockets directly."""

    @abstractmethod
    def send(self, data: bytes) -> None: ...

    @abstractmethod
    def recv(self) -> bytes: ...


class InMemoryChannel(Channel):
    """In-process Channel backed by two queues — a test double for the transport."""

    _CLOSED = None

    def __init__(self, in_q: queue.Queue, out_q: queue.Queue) -> None:
        self._in_q = in_q
        self._out_q = out_q

    def send(self, data: bytes) -> None:
        self._out_q.put(data)

    def recv(self) -> bytes:
        data = self._in_q.get()
        if data is self._CLOSED:
            raise ConnectionClosedError("peer closed the connection")
        return data

    def close(self) -> None:
        self._out_q.put(self._CLOSED)

    @classmethod
    def make_pair(cls) -> tuple["InMemoryChannel", "InMemoryChannel"]:
        q_a: queue.Queue = queue.Queue()
        q_b: queue.Queue = queue.Queue()
        return cls(q_a, q_b), cls(q_b, q_a)


class FramedChannel(Channel):
    """Channel decorator that implements length-prefix framing (T2.2)."""

    def __init__(self, inner: Channel, max_bytes: int = 10485760) -> None:
        self._inner = inner
        self._max_bytes = max_bytes
        self._read_buffer = bytearray()

    def send(self, data: bytes) -> None:
        from agent_arena.shared.transport.framing import send_frame
        send_frame(self._inner, data)

    def recv(self) -> bytes:
        import struct
        header_size = 4
        while len(self._read_buffer) < header_size:
            chunk = self._inner.recv()
            if not chunk:
                raise ConnectionClosedError("peer closed connection mid-frame")
            self._read_buffer.extend(chunk)

        (payload_length,) = struct.unpack(">I", bytes(self._read_buffer[:header_size]))
        if payload_length > self._max_bytes:
            from agent_arena.shared.transport.framing import FrameTooLargeError
            raise FrameTooLargeError(
                f"frame declares {payload_length} bytes; max is {self._max_bytes}"
            )

        total_size = header_size + payload_length
        while len(self._read_buffer) < total_size:
            chunk = self._inner.recv()
            if not chunk:
                raise ConnectionClosedError("peer closed connection mid-frame")
            self._read_buffer.extend(chunk)

        payload = bytes(self._read_buffer[header_size:total_size])
        self._read_buffer = self._read_buffer[total_size:]
        return payload

    def close(self) -> None:
        if hasattr(self._inner, "close"):
            self._inner.close()

