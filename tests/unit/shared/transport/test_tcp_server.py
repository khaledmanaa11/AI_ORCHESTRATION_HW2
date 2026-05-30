"""Unit tests for agent_arena.shared.transport.tcp_server using real localhost sockets."""
import socket
import struct
import threading
import time

from agent_arena.shared.transport.channel import Channel
from agent_arena.shared.transport.framing import send_frame
from agent_arena.shared.transport.tcp_server import TcpServer

_HOST = "127.0.0.1"
_HEADER_SIZE = 4


def _connect(port: int) -> socket.socket:
    return socket.create_connection((_HOST, port), timeout=2.0)


def _noop(_channel: Channel) -> None:
    pass


def _recv_exact(sock: socket.socket, size: int) -> bytes:
    data = bytearray()
    while len(data) < size:
        chunk = sock.recv(size - len(data))
        if not chunk:
            break
        data.extend(chunk)
    return bytes(data)


def test_two_clients_trigger_on_connect_twice():
    count = {"n": 0}
    lock = threading.Lock()

    def on_connect(_channel: Channel) -> None:
        with lock:
            count["n"] += 1

    server = TcpServer(_HOST, 0, player_count=2, on_connect=on_connect)
    server.start()
    try:
        c1 = _connect(server.port)
        c2 = _connect(server.port)
        time.sleep(0.2)
        assert count["n"] == 2
    finally:
        c1.close()
        c2.close()
        server.stop()


def test_third_client_receives_reject_frame_before_eof():
    def on_reject(channel: Channel) -> None:
        send_frame(channel, b"match full")

    server = TcpServer(_HOST, 0, player_count=2, on_connect=_noop, on_reject=on_reject)
    server.start()
    try:
        c1 = _connect(server.port)
        c2 = _connect(server.port)
        time.sleep(0.2)
        c3 = _connect(server.port)
        c3.settimeout(2.0)
        header = _recv_exact(c3, _HEADER_SIZE)
        (payload_length,) = struct.unpack(">I", header)
        assert _recv_exact(c3, payload_length) == b"match full"
        assert c3.recv(1) == b""
    finally:
        c1.close()
        c2.close()
        c3.close()
        server.stop()


def test_data_reaches_handler():
    received: list[bytes] = []
    done = threading.Event()

    def on_connect(channel: Channel) -> None:
        received.append(channel.recv())
        done.set()

    server = TcpServer(_HOST, 0, player_count=1, on_connect=on_connect)
    server.start()
    try:
        c1 = _connect(server.port)
        c1.sendall(b"ping")
        assert done.wait(timeout=2.0)
        assert received == [b"ping"]
    finally:
        c1.close()
        server.stop()


def test_stop_terminates_accept_loop():
    server = TcpServer(_HOST, 0, player_count=5, on_connect=_noop)
    server.start()
    accept_thread = server._accept_thread
    server.stop()
    accept_thread.join(timeout=2.0)
    assert not accept_thread.is_alive()
