"""Unit tests for agent_arena.shared.transport.tcp_client over real localhost sockets."""
import socket
import threading

import pytest

from agent_arena.shared.transport.channel import Channel
from agent_arena.shared.transport.tcp_client import ConnectionFailedError, TcpClient

_HOST = "127.0.0.1"


def _listening_socket() -> socket.socket:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    s.bind((_HOST, 0))
    s.listen()
    return s


def _free_port() -> int:
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind((_HOST, 0))
    port = s.getsockname()[1]
    s.close()
    return port


def test_connect_returns_channel():
    server = _listening_socket()
    port = server.getsockname()[1]
    try:
        client = TcpClient(_HOST, port, connect_timeout=2.0, max_retries=1, backoff_base=0.01)
        ch = client.connect()
        assert isinstance(ch, Channel)
        client.close()
    finally:
        server.close()


def test_connect_exhausts_retries_and_raises():
    port = _free_port()  # nothing listening here
    client = TcpClient(_HOST, port, connect_timeout=0.5, max_retries=1, backoff_base=0.01)
    with pytest.raises(ConnectionFailedError):
        client.connect()


def test_data_flows_over_connection():
    server = _listening_socket()
    port = server.getsockname()[1]
    received: list[bytes] = []
    done = threading.Event()

    def accept() -> None:
        conn, _ = server.accept()
        received.append(conn.recv(4096))
        done.set()
        conn.close()

    threading.Thread(target=accept, daemon=True).start()
    try:
        client = TcpClient(_HOST, port, connect_timeout=2.0, max_retries=1, backoff_base=0.01)
        ch = client.connect()
        ch.send(b"payload")
        assert done.wait(timeout=2.0)
        assert received == [b"payload"]
        client.close()
    finally:
        server.close()
