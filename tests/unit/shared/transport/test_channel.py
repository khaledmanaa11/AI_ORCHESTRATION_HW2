"""Unit tests for agent_arena.shared.transport.channel."""
import threading

import pytest

from agent_arena.shared.transport.channel import (
    Channel,
    ConnectionClosedError,
    InMemoryChannel,
)


def test_make_pair_send_a_recv_b():
    a, b = InMemoryChannel.make_pair()
    a.send(b"hello")
    assert b.recv() == b"hello"


def test_bidirectional():
    a, b = InMemoryChannel.make_pair()
    b.send(b"from-b")
    assert a.recv() == b"from-b"
    a.send(b"from-a")
    assert b.recv() == b"from-a"


def test_close_raises_connection_closed():
    a, b = InMemoryChannel.make_pair()
    a.close()
    with pytest.raises(ConnectionClosedError):
        b.recv()


def test_is_instance_of_channel():
    a, _ = InMemoryChannel.make_pair()
    assert isinstance(a, Channel)


def test_channel_is_abstract():
    with pytest.raises(TypeError):
        Channel()


def test_thread_safety_many_senders():
    a, b = InMemoryChannel.make_pair()
    n_threads, per_thread = 10, 100

    def spam() -> None:
        for _ in range(per_thread):
            a.send(b"x")

    threads = [threading.Thread(target=spam) for _ in range(n_threads)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    received = 0
    for _ in range(n_threads * per_thread):
        assert b.recv() == b"x"
        received += 1
    assert received == n_threads * per_thread
