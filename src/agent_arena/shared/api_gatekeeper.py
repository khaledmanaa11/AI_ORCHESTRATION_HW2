import logging
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Literal, Optional

from agent_arena.shared.config import load_setup_config

logger = logging.getLogger(__name__)

_DEFAULT_GATEKEEPER: Optional["APIGatekeeper"] = None
_DEFAULT_GATEKEEPER_LOCK = threading.Lock()


def get_default_gatekeeper() -> "APIGatekeeper":
    global _DEFAULT_GATEKEEPER
    if _DEFAULT_GATEKEEPER is None:
        with _DEFAULT_GATEKEEPER_LOCK:
            if _DEFAULT_GATEKEEPER is None:
                setup = load_setup_config("config/setup.json")
                _DEFAULT_GATEKEEPER = APIGatekeeper(**setup.llm.gatekeeper.model_dump())
    return _DEFAULT_GATEKEEPER


class GatekeeperError(Exception):
    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason

    def __str__(self) -> str:
        return self.reason


class GatekeeperOpenError(GatekeeperError):
    pass


class GatekeeperExhaustedError(GatekeeperError):
    pass


class GatekeeperTimeoutError(GatekeeperError):
    pass


class _BreakerState(Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class OutcomeRecorder:
    def __init__(self) -> None:
        self.outcome: Literal["success", "retryable_error", "fatal_error"] = "fatal_error"

    def record(self, outcome: Literal["success", "retryable_error", "fatal_error"]) -> None:
        self.outcome = outcome


class APIGatekeeper:
    def __init__(
        self,
        *,
        rpm: int,
        rpd: int,
        max_concurrency: int,
        breaker_threshold: int,
        breaker_window_seconds: float,
        breaker_cooldown_seconds: float,
        acquire_timeout_seconds: float,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._rpm = rpm
        self._rpd = rpd
        self._max_concurrency = max_concurrency
        self._breaker_threshold = breaker_threshold
        self._breaker_window_seconds = breaker_window_seconds
        self._breaker_cooldown_seconds = breaker_cooldown_seconds
        self._acquire_timeout_seconds = acquire_timeout_seconds
        self._clock = clock

        self._tokens = float(rpm)
        self._last_refill = self._clock()
        self._rpd_remaining = rpd
        self._rpd_reset_at = self._next_utc_midnight(datetime.now(timezone.utc))

        self._in_flight = 0
        self._breaker = _BreakerState.CLOSED
        self._consecutive_failures = 0
        self._failure_window_start: float | None = None
        self._opened_at: float | None = None
        self._half_open_probe_in_flight = False

        self._lock = threading.Lock()
        self._cond = threading.Condition(self._lock)

    @staticmethod
    def _next_utc_midnight(now: datetime) -> datetime:
        return (now + timedelta(days=1)).replace(
            hour=0, minute=0, second=0, microsecond=0
        )

    def _refill_locked(self) -> None:
        now = self._clock()
        elapsed = max(0.0, now - self._last_refill)
        self._tokens = min(float(self._rpm), self._tokens + elapsed * (self._rpm / 60.0))
        self._last_refill = now

    def _check_rpd_reset_locked(self) -> None:
        now = datetime.now(timezone.utc)
        if now >= self._rpd_reset_at:
            self._rpd_remaining = self._rpd
            self._rpd_reset_at = self._next_utc_midnight(now)
            logger.warning("Gatekeeper RPD reset at %s", self._rpd_reset_at.isoformat())

    def _maybe_transition_open_to_half_open_locked(self) -> None:
        if self._breaker != _BreakerState.OPEN or self._opened_at is None:
            return
        if self._clock() - self._opened_at < self._breaker_cooldown_seconds:
            return
        self._breaker = _BreakerState.HALF_OPEN
        self._half_open_probe_in_flight = False
        logger.info("Gatekeeper breaker OPEN → HALF_OPEN")

    def _trip_breaker_locked(self, reason: str) -> None:
        self._breaker = _BreakerState.OPEN
        self._opened_at = self._clock()
        self._half_open_probe_in_flight = False
        self._consecutive_failures = 0
        self._failure_window_start = None
        logger.warning("Gatekeeper breaker OPEN: %s", reason)

    def acquire(self, *, timeout: float | None = None) -> None:
        timeout = timeout if timeout is not None else self._acquire_timeout_seconds
        start = self._clock()
        deadline = start + timeout

        with self._cond:
            while True:
                self._check_rpd_reset_locked()
                self._maybe_transition_open_to_half_open_locked()

                if self._breaker == _BreakerState.OPEN:
                    raise GatekeeperOpenError("Gatekeeper circuit is open")
                if self._breaker == _BreakerState.HALF_OPEN and self._half_open_probe_in_flight:
                    raise GatekeeperOpenError("Gatekeeper half-open probe already in flight")
                if self._rpd_remaining <= 0:
                    raise GatekeeperExhaustedError(
                        f"RPD exhausted until {self._rpd_reset_at.isoformat()}"
                    )

                self._refill_locked()
                if self._tokens >= 1.0 and self._in_flight < self._max_concurrency:
                    break

                remaining = deadline - self._clock()
                if remaining <= 0:
                    raise GatekeeperTimeoutError(
                        f"timed out after {timeout:.1f}s waiting for slot/token"
                    )

                self._cond.wait(timeout=remaining)

            self._tokens -= 1.0
            self._rpd_remaining -= 1
            self._in_flight += 1
            if self._breaker == _BreakerState.HALF_OPEN:
                self._half_open_probe_in_flight = True

        waited = self._clock() - start
        if waited > 1.0:
            logger.warning("Gatekeeper acquire waited %.2fs for slot/token", waited)

    def release(self, *, outcome: Literal["success", "retryable_error", "fatal_error"]) -> None:
        with self._cond:
            if self._in_flight > 0:
                self._in_flight -= 1

            if self._breaker == _BreakerState.HALF_OPEN:
                self._half_open_probe_in_flight = False
                if outcome == "success":
                    self._breaker = _BreakerState.CLOSED
                    self._consecutive_failures = 0
                    self._failure_window_start = None
                    logger.info("Gatekeeper breaker HALF_OPEN → CLOSED")
                else:
                    self._trip_breaker_locked("half-open probe failed")
            else:
                if outcome == "success":
                    self._consecutive_failures = 0
                    self._failure_window_start = None
                elif outcome == "retryable_error":
                    now = self._clock()
                    if (
                        self._failure_window_start is None
                        or now - self._failure_window_start > self._breaker_window_seconds
                    ):
                        self._consecutive_failures = 1
                        self._failure_window_start = now
                    else:
                        self._consecutive_failures += 1
                    if self._consecutive_failures >= self._breaker_threshold:
                        self._trip_breaker_locked(
                            f"{self._consecutive_failures} retryable errors in {self._breaker_window_seconds}s"
                        )
                else:
                    # fatal_error does not count toward breaker tripping.
                    pass

            self._cond.notify_all()

    @contextmanager
    def gate(self, *, timeout: float | None = None) -> Iterator[OutcomeRecorder]:
        recorder = OutcomeRecorder()
        acquired = False
        try:
            self.acquire(timeout=timeout)
            acquired = True
            yield recorder
        except GatekeeperError:
            raise
        except Exception:
            if acquired:
                recorder.record("fatal_error")
            raise
        finally:
            if acquired:
                self.release(outcome=recorder.outcome)

    def snapshot(self) -> dict[str, object]:
        with self._lock:
            return {
                "rpm_tokens": self._tokens,
                "rpd_remaining": self._rpd_remaining,
                "rpd_resets_at": self._rpd_reset_at.isoformat(),
                "in_flight": self._in_flight,
                "max_concurrency": self._max_concurrency,
                "breaker_state": self._breaker.name,
                "consecutive_failures": self._consecutive_failures,
                "breaker_opened_at": (
                    datetime.fromtimestamp(self._opened_at, timezone.utc).isoformat()
                    if self._opened_at is not None
                    else None
                ),
            }
