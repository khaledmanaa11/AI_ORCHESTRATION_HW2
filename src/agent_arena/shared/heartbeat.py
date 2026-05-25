import logging
import threading
from collections.abc import Callable

logger = logging.getLogger(__name__)


class HeartbeatSender(threading.Thread):
    """Daemon thread that periodically calls send_fn to keep a connection alive."""

    def __init__(
        self,
        interval_seconds: float,
        send_fn: Callable[[], None],
        shutdown_event: threading.Event,
    ) -> None:
        super().__init__(daemon=True, name="heartbeat-sender")
        self._interval = interval_seconds
        self._send_fn = send_fn
        self._shutdown_event = shutdown_event
        self._stop_event = threading.Event()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        def _should_stop() -> bool:
            return self._stop_event.is_set() or self._shutdown_event.is_set()

        # Wait one full interval before the first send (C5.8).
        while not self._stop_event.wait(self._interval):
            if _should_stop():
                break
            try:
                self._send_fn()
                logger.debug("Heartbeat sent")
            except Exception:
                logger.exception("send_fn raised an exception; stopping heartbeat sender")
                break
