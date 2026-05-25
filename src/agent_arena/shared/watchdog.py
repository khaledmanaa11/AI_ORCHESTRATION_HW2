import logging
import threading
import time
from collections.abc import Callable

logger = logging.getLogger(__name__)


class WatchdogThread(threading.Thread):
    """Daemon thread that monitors named peers and fires a one-shot callback on silence."""

    def __init__(
        self,
        timeout_seconds: float,
        on_timeout: Callable[[str], None],
        check_interval_seconds: float = 1.0,
    ) -> None:
        super().__init__(daemon=True, name="watchdog")
        self._timeout = timeout_seconds
        self._on_timeout = on_timeout
        self._check_interval = check_interval_seconds
        self._last_seen: dict[str, float] = {}
        self._fired: set[str] = set()
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

    def register(self, peer: str) -> None:
        with self._lock:
            self._last_seen[peer] = time.monotonic()

    def heartbeat(self, peer: str) -> None:
        with self._lock:
            if peer not in self._last_seen:
                return
            self._last_seen[peer] = time.monotonic()

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.wait(self._check_interval):
            now = time.monotonic()
            with self._lock:
                snapshot = list(self._last_seen.items())
            logger.debug("Watchdog checking %d peer(s)", len(snapshot))
            for peer, last_seen_time in snapshot:
                elapsed = now - last_seen_time
                if elapsed > self._timeout and peer not in self._fired:
                    logger.warning(
                        "Watchdog timeout for peer %r (elapsed %.2f s)", peer, elapsed
                    )
                    self._fired.add(peer)
                    try:
                        self._on_timeout(peer)
                    except Exception:
                        logger.exception("on_timeout callback for peer %r raised", peer)
