"""Unit tests for agent_arena.shared.shutdown — ShutdownCoordinator."""
import threading
import time
from unittest import mock

from agent_arena.shared.shutdown import ShutdownCoordinator


def test_is_shutdown_false_initially():
    coord = ShutdownCoordinator()
    assert coord.is_shutdown() is False


def test_is_shutdown_true_after_request():
    coord = ShutdownCoordinator()
    coord.request_shutdown("test")
    assert coord.is_shutdown() is True


def test_registered_callback_is_called():
    coord = ShutdownCoordinator()
    cb = mock.MagicMock()
    coord.register_callback(cb)
    coord.request_shutdown("test")
    assert cb.called


def test_callbacks_called_in_order():
    coord = ShutdownCoordinator()
    call_order: list[str] = []
    coord.register_callback(lambda: call_order.append("A"))
    coord.register_callback(lambda: call_order.append("B"))
    coord.request_shutdown("test")
    assert call_order == ["A", "B"]


def test_idempotent_shutdown():
    coord = ShutdownCoordinator()
    cb = mock.MagicMock()
    coord.register_callback(cb)
    coord.request_shutdown("first")
    coord.request_shutdown("second")
    assert cb.call_count == 1


def test_raising_callback_does_not_prevent_next():
    coord = ShutdownCoordinator()
    call_order: list[str] = []

    def raiser() -> None:
        raise RuntimeError("boom")

    coord.register_callback(raiser)
    coord.register_callback(lambda: call_order.append("B"))
    coord.request_shutdown("test")
    assert "B" in call_order


def test_wait_returns_false_before_shutdown():
    coord = ShutdownCoordinator()
    result = coord.wait(timeout=0.0)
    assert result is False


def test_wait_returns_true_when_shutdown_triggered_from_thread():
    coord = ShutdownCoordinator()

    def delayed_shutdown() -> None:
        time.sleep(0.05)
        coord.request_shutdown("thread")

    t = threading.Thread(target=delayed_shutdown)
    t.start()
    result = coord.wait(timeout=1.0)
    t.join()
    assert result is True


def test_thread_safety_callbacks_called_once():
    coord = ShutdownCoordinator()
    cb = mock.MagicMock()
    coord.register_callback(cb)
    threads = [
        threading.Thread(target=lambda: coord.request_shutdown("concurrent"))
        for _ in range(10)
    ]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert cb.call_count == 1


def test_late_registered_callback_not_called():
    coord = ShutdownCoordinator()
    coord.request_shutdown("test")
    late_cb = mock.MagicMock()
    coord.register_callback(late_cb)
    assert late_cb.call_count == 0


def test_no_config_required():
    coord = ShutdownCoordinator()
    assert coord is not None


def test_install_signal_handlers_does_not_raise():
    coord = ShutdownCoordinator()
    coord.install_signal_handlers()
    assert coord.is_shutdown() is False
