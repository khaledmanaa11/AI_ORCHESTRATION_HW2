"""Unit tests for agent_arena.shared.heartbeat — HeartbeatSender."""
import threading
import time
from unittest import mock

from agent_arena.shared.heartbeat import HeartbeatSender

_INTERVAL = 0.05  # 50 ms — fast enough for tests, slow enough to be reliable on CI


def _make_sender(
    send_fn: mock.MagicMock | None = None,
    shutdown_event: threading.Event | None = None,
) -> HeartbeatSender:
    if send_fn is None:
        send_fn = mock.MagicMock()
    if shutdown_event is None:
        shutdown_event = threading.Event()
    return HeartbeatSender(
        interval_seconds=_INTERVAL,
        send_fn=send_fn,
        shutdown_event=shutdown_event,
    )


def test_daemon_and_name():
    hs = _make_sender()
    assert hs.daemon is True
    assert hs.name == "heartbeat-sender"


def test_send_fn_called_after_interval():
    fn = mock.MagicMock()
    hs = _make_sender(send_fn=fn)
    hs.start()
    time.sleep(_INTERVAL * 5)
    hs.stop()
    hs.join(timeout=1.0)
    assert fn.call_count >= 1


def test_send_fn_called_approximately_n_times():
    fn = mock.MagicMock()
    hs = _make_sender(send_fn=fn)
    hs.start()
    time.sleep(_INTERVAL * 6)
    hs.stop()
    hs.join(timeout=1.0)
    # Generous range to tolerate CI scheduling jitter.
    assert 2 <= fn.call_count <= 7


def test_stop_prevents_further_calls():
    fn = mock.MagicMock()
    hs = _make_sender(send_fn=fn)
    hs.start()
    time.sleep(_INTERVAL * 3)
    hs.stop()
    hs.join(timeout=1.0)
    count_at_stop = fn.call_count
    time.sleep(_INTERVAL * 4)
    assert fn.call_count == count_at_stop


def test_shutdown_event_stops_sender():
    fn = mock.MagicMock()
    shutdown = threading.Event()
    hs = HeartbeatSender(interval_seconds=_INTERVAL, send_fn=fn, shutdown_event=shutdown)
    hs.start()
    time.sleep(_INTERVAL * 2)
    shutdown.set()
    hs.join(timeout=1.0)
    count_at_shutdown = fn.call_count
    time.sleep(_INTERVAL * 4)
    assert fn.call_count == count_at_shutdown


def test_raising_send_fn_stops_thread():
    def always_raises() -> None:
        raise RuntimeError("network gone")

    shutdown = threading.Event()
    hs = HeartbeatSender(
        interval_seconds=_INTERVAL, send_fn=always_raises, shutdown_event=shutdown
    )
    hs.start()
    hs.join(timeout=1.0)
    assert not hs.is_alive(), "thread must exit after send_fn raises"


def test_send_fn_not_called_immediately_on_start():
    fn = mock.MagicMock()
    hs = _make_sender(send_fn=fn)
    hs.start()
    # Check immediately — must be 0 because the first send waits one full interval.
    assert fn.call_count == 0
    time.sleep(_INTERVAL + 0.03)
    assert fn.call_count >= 1
    hs.stop()
    hs.join(timeout=1.0)
