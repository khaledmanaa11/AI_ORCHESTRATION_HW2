import logging
import signal
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)


class ShutdownCoordinator:
    """Single authority for process-level shutdown. Thread-safe. Callbacks run exactly once."""

    def __init__(self) -> None:
        self._event = threading.Event()
        self._callbacks: list[Callable[[], None]] = []
        self._lock = threading.Lock()

    def register_callback(self, fn: Callable[[], None]) -> None:
        with self._lock:
            self._callbacks.append(fn)

    def request_shutdown(self, reason: str) -> None:
        with self._lock:
            if self._event.is_set():
                return
            self._event.set()
            callbacks = list(self._callbacks)
        logger.warning("Shutdown requested: %s", reason)
        for cb in callbacks:
            try:
                cb()
            except Exception:
                logger.exception("Shutdown callback %r raised an exception", cb)

    def is_shutdown(self) -> bool:
        return self._event.is_set()

    def wait(self, timeout: float | None = None) -> bool:
        return self._event.wait(timeout)

    def install_signal_handlers(self) -> None:
        def _make_handler(name: str) -> Callable[[int, object], None]:
            def _handler(signum: int, frame: object) -> None:  # noqa: ARG001
                self.request_shutdown(f"signal:{name}")

            return _handler

        try:
            signal.signal(signal.SIGTERM, _make_handler("SIGTERM"))
        except OSError:
            logger.warning("Could not install SIGTERM handler (not supported on this platform)")
        signal.signal(signal.SIGINT, _make_handler("SIGINT"))
