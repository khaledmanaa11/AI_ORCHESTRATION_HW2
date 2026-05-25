"""Unit tests for agent_arena.shared.watchdog — WatchdogThread."""
import threading
import time
from unittest import mock

from agent_arena.shared.watchdog import WatchdogThread

# Short durations keep the test suite fast while remaining reliable on CI.
_TIMEOUT = 0.2
_INTERVAL = 0.05


def _make_wd(on_timeout: mock.MagicMock | None = None) -> WatchdogThread:
    if on_timeout is None:
        on_timeout = mock.MagicMock()
    return WatchdogThread(
        timeout_seconds=_TIMEOUT,
        on_timeout=on_timeout,
        check_interval_seconds=_INTERVAL,
    )


def test_daemon_and_name():
    wd = _make_wd()
    assert wd.daemon is True
    assert wd.name == "watchdog"


def test_no_timeout_when_heartbeats_arrive():
    cb = mock.MagicMock()
    wd = WatchdogThread(timeout_seconds=_TIMEOUT, on_timeout=cb, check_interval_seconds=_INTERVAL)
    wd.register("p1")
    wd.start()
    # Send heartbeats well within the timeout window.
    end = time.monotonic() + _TIMEOUT * 1.5
    while time.monotonic() < end:
        wd.heartbeat("p1")
        time.sleep(_INTERVAL / 2)
    wd.stop()
    wd.join(timeout=1.0)
    assert cb.call_count == 0


def test_timeout_fires_for_silent_peer():
    cb = mock.MagicMock()
    wd = WatchdogThread(timeout_seconds=_TIMEOUT, on_timeout=cb, check_interval_seconds=_INTERVAL)
    wd.register("p1")
    wd.start()
    # Wait long enough for the watchdog to detect silence.
    time.sleep(_TIMEOUT + _INTERVAL + 0.1)
    wd.stop()
    wd.join(timeout=1.0)
    cb.assert_called_once_with("p1")


def test_timeout_fires_exactly_once():
    cb = mock.MagicMock()
    wd = WatchdogThread(timeout_seconds=_TIMEOUT, on_timeout=cb, check_interval_seconds=_INTERVAL)
    wd.register("p1")
    wd.start()
    # Wait for three check cycles past the timeout.
    time.sleep(_TIMEOUT + _INTERVAL * 3 + 0.1)
    wd.stop()
    wd.join(timeout=1.0)
    assert cb.call_count == 1


def test_repeated_heartbeats_reset_timer():
    cb = mock.MagicMock()
    wd = WatchdogThread(timeout_seconds=_TIMEOUT, on_timeout=cb, check_interval_seconds=_INTERVAL)
    wd.register("p1")
    wd.start()
    # Heartbeat every half-interval for three timeout windows.
    end = time.monotonic() + _TIMEOUT * 3
    while time.monotonic() < end:
        wd.heartbeat("p1")
        time.sleep(_INTERVAL / 2)
    wd.stop()
    wd.join(timeout=1.0)
    assert cb.call_count == 0


def test_stop_prevents_callback():
    cb = mock.MagicMock()
    wd = WatchdogThread(timeout_seconds=_TIMEOUT, on_timeout=cb, check_interval_seconds=_INTERVAL)
    wd.register("p1")
    wd.start()
    # Stop immediately, before the timeout would fire.
    wd.stop()
    wd.join(timeout=1.0)
    time.sleep(_TIMEOUT + 0.1)
    assert cb.call_count == 0


def test_two_peers_only_silent_one_times_out():
    cb = mock.MagicMock()
    wd = WatchdogThread(timeout_seconds=_TIMEOUT, on_timeout=cb, check_interval_seconds=_INTERVAL)
    wd.register("p1")
    wd.register("p2")
    wd.start()
    # Keep p2 alive; let p1 go silent.
    end = time.monotonic() + _TIMEOUT + _INTERVAL + 0.1
    while time.monotonic() < end:
        wd.heartbeat("p2")
        time.sleep(_INTERVAL / 2)
    wd.stop()
    wd.join(timeout=1.0)
    cb.assert_called_once_with("p1")


def test_heartbeat_for_unregistered_peer_does_not_raise():
    wd = _make_wd()
    wd.heartbeat("ghost")  # must not raise


def test_concurrent_heartbeats_do_not_corrupt_state():
    wd = _make_wd()
    wd.register("p1")
    wd.start()

    def spam() -> None:
        for _ in range(100):
            wd.heartbeat("p1")

    threads = [threading.Thread(target=spam) for _ in range(20)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    wd.stop()
    wd.join(timeout=1.0)
    with wd._lock:
        assert isinstance(wd._last_seen["p1"], float)


def test_raising_on_timeout_does_not_crash_watchdog():
    def bad_callback(peer: str) -> None:  # noqa: ARG001
        raise RuntimeError("oops")

    wd = WatchdogThread(
        timeout_seconds=_TIMEOUT, on_timeout=bad_callback, check_interval_seconds=_INTERVAL
    )
    wd.register("p1")
    wd.start()
    time.sleep(_TIMEOUT + _INTERVAL + 0.1)
    assert wd.is_alive(), "watchdog thread must survive a raising on_timeout callback"
    wd.stop()
    wd.join(timeout=1.0)


def test_timeout_seconds_param_is_used_not_hardcoded():
    cb = mock.MagicMock()
    # Use an even shorter explicit timeout to prove the param drives the behaviour.
    wd = WatchdogThread(timeout_seconds=0.1, on_timeout=cb, check_interval_seconds=0.03)
    wd.register("p1")
    wd.start()
    time.sleep(0.1 + 0.03 + 0.05)
    wd.stop()
    wd.join(timeout=1.0)
    cb.assert_called_once_with("p1")
