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
