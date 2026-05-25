import contextlib
import logging
import socket
import threading
from collections.abc import Callable

from agent_arena.shared.transport.channel import Channel, ConnectionClosedError

logger = logging.getLogger(__name__)


class TcpChannel(Channel):
    """Channel wrapping a single accepted/connected TCP socket."""

    def __init__(self, sock: socket.socket) -> None:
        self._sock = sock

    def send(self, data: bytes) -> None:
        self._sock.sendall(data)

    def recv(self) -> bytes:
        data = self._sock.recv(4096)
        if data == b"":
            raise ConnectionClosedError("peer closed the TCP connection")
        return data

    def close(self) -> None:
        with contextlib.suppress(OSError):
            self._sock.close()


class TcpServer:
    """Binds a listen socket and dispatches one daemon thread per accepted connection."""

    def __init__(
        self,
        host: str,
        port: int,
        player_count: int,
        on_connect: Callable[[Channel], None],
    ) -> None:
        self._host = host
        self._port = port
        self._player_count = player_count
        self._on_connect = on_connect
        self._sock: socket.socket | None = None
        self._accept_thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        if self._sock is None:
            return self._port
        return self._sock.getsockname()[1]

    def start(self) -> None:
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._sock.bind((self._host, self._port))
        self._sock.listen()
        logger.info("TcpServer listening on %s:%d", self._host, self.port)
        self._accept_thread = threading.Thread(
            target=self._accept_loop, daemon=True, name="tcp-accept"
        )
        self._accept_thread.start()

    def _accept_loop(self) -> None:
        accepted = 0
        while accepted < self._player_count:
            try:
                conn, addr = self._sock.accept()
            except OSError:
                return
            accepted += 1
            logger.info("Accepted connection %d/%d from %s", accepted, self._player_count, addr)
            threading.Thread(
                target=self._on_connect,
                args=(TcpChannel(conn),),
                daemon=True,
                name=f"tcp-handler-{accepted}",
            ).start()
        self._reject_extras()

    def _reject_extras(self) -> None:
        while True:
            try:
                conn, addr = self._sock.accept()
            except OSError:
                return
            logger.warning("Rejecting extra connection from %s", addr)
            TcpChannel(conn).close()

    def stop(self) -> None:
        if self._sock is not None:
            with contextlib.suppress(OSError):
                self._sock.close()
