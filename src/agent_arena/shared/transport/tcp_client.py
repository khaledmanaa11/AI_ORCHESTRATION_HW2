import contextlib
import logging
import socket
import time

from agent_arena.shared.transport.channel import Channel
from agent_arena.shared.transport.tcp_server import TcpChannel

logger = logging.getLogger(__name__)


class ConnectionFailedError(IOError):
    """Raised when all connection attempts to the server are exhausted."""


class TcpClient:
    """Outbound TCP connector with exponential-backoff retry."""

    def __init__(
        self,
        host: str,
        port: int,
        connect_timeout: float,
        max_retries: int,
        backoff_base: float,
    ) -> None:
        self._host = host
        self._port = port
        self._connect_timeout = connect_timeout
        self._max_retries = max_retries
        self._backoff_base = backoff_base
        self._sock: socket.socket | None = None

    def connect(self) -> Channel:
        for attempt in range(self._max_retries + 1):
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(self._connect_timeout)
            try:
                sock.connect((self._host, self._port))
            except (ConnectionRefusedError, TimeoutError) as exc:
                sock.close()
                if attempt >= self._max_retries:
                    break
                wait = self._backoff_base * (2 ** attempt)
                logger.warning(
                    "Connect failed (attempt %d: %s); retrying in %.2f s",
                    attempt + 1, exc, wait,
                )
                time.sleep(wait)
                continue
            except OSError as exc:
                sock.close()
                raise ConnectionFailedError(
                    f"failed to connect to {self._host}:{self._port}"
                ) from exc
            sock.settimeout(None)
            self._sock = sock
            logger.info("Connected to %s:%d", self._host, self._port)
            return TcpChannel(sock)
        raise ConnectionFailedError(
            f"failed to connect to {self._host}:{self._port} after "
            f"{self._max_retries + 1} attempt(s)"
        )

    def close(self) -> None:
        if self._sock is not None:
            with contextlib.suppress(OSError):
                self._sock.close()
