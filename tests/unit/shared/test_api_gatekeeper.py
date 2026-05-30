"""Unit tests for agent_arena.shared.api_gatekeeper."""

import json
from datetime import datetime, timedelta, timezone

import pytest

from agent_arena.shared.api_gatekeeper import (
    APIGatekeeper,
    GatekeeperExhaustedError,
    GatekeeperOpenError,
    GatekeeperTimeoutError,
)


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


def _make_gatekeeper(
    clock: FakeClock,
    *,
    rpm: int = 60,
    rpd: int = 100,
    max_concurrency: int = 1,
    breaker_threshold: int = 2,
    breaker_window_seconds: float = 10.0,
    breaker_cooldown_seconds: float = 5.0,
    acquire_timeout_seconds: float = 1.0,
) -> APIGatekeeper:
    return APIGatekeeper(
        rpm=rpm,
        rpd=rpd,
        max_concurrency=max_concurrency,
        breaker_threshold=breaker_threshold,
        breaker_window_seconds=breaker_window_seconds,
        breaker_cooldown_seconds=breaker_cooldown_seconds,
        acquire_timeout_seconds=acquire_timeout_seconds,
        clock=clock,
    )


def _trip_breaker(gatekeeper: APIGatekeeper) -> None:
    for _ in range(2):
        gatekeeper.acquire()
        gatekeeper.release(outcome="retryable_error")


def test_token_bucket_refills_and_caps_at_rpm() -> None:
    clock = FakeClock()
    gatekeeper = _make_gatekeeper(clock, rpm=2)

    gatekeeper.acquire()
    gatekeeper.release(outcome="success")
    gatekeeper.acquire()
    gatekeeper.release(outcome="success")
    assert gatekeeper.snapshot()["rpm_tokens"] == 0.0

    clock.advance(60.0)
    gatekeeper.acquire()

    assert gatekeeper.snapshot()["rpm_tokens"] == 1.0


def test_rpd_limit_exhausts_and_resets_at_daily_boundary() -> None:
    clock = FakeClock()
    gatekeeper = _make_gatekeeper(clock, rpd=1)

    gatekeeper.acquire()
    gatekeeper.release(outcome="success")

    with pytest.raises(GatekeeperExhaustedError):
        gatekeeper.acquire()

    gatekeeper._rpd_reset_at = datetime.now(timezone.utc) - timedelta(seconds=1)
    gatekeeper.acquire()

    assert gatekeeper.snapshot()["rpd_remaining"] == 0


def test_breaker_trips_after_retryable_errors_within_window_and_rejects() -> None:
    clock = FakeClock()
    gatekeeper = _make_gatekeeper(clock)

    _trip_breaker(gatekeeper)

    assert gatekeeper.snapshot()["breaker_state"] == "OPEN"
    with pytest.raises(GatekeeperOpenError):
        gatekeeper.acquire()


def test_breaker_retryable_error_window_resets() -> None:
    clock = FakeClock()
    gatekeeper = _make_gatekeeper(clock, breaker_window_seconds=5.0)

    gatekeeper.acquire()
    gatekeeper.release(outcome="retryable_error")
    clock.advance(6.0)
    gatekeeper.acquire()
    gatekeeper.release(outcome="retryable_error")

    assert gatekeeper.snapshot()["breaker_state"] == "CLOSED"

    gatekeeper.acquire()
    gatekeeper.release(outcome="retryable_error")

    assert gatekeeper.snapshot()["breaker_state"] == "OPEN"


def test_open_breaker_transitions_to_half_open_after_cooldown() -> None:
    clock = FakeClock()
    gatekeeper = _make_gatekeeper(clock, breaker_cooldown_seconds=5.0)
    _trip_breaker(gatekeeper)

    clock.advance(5.0)
    gatekeeper.acquire()

    snapshot = gatekeeper.snapshot()
    assert snapshot["breaker_state"] == "HALF_OPEN"
    assert snapshot["in_flight"] == 1

    with pytest.raises(GatekeeperOpenError):
        gatekeeper.acquire()


def test_half_open_success_closes_breaker() -> None:
    clock = FakeClock()
    gatekeeper = _make_gatekeeper(clock, breaker_cooldown_seconds=5.0)
    _trip_breaker(gatekeeper)

    clock.advance(5.0)
    gatekeeper.acquire()
    gatekeeper.release(outcome="success")

    assert gatekeeper.snapshot()["breaker_state"] == "CLOSED"


def test_half_open_failure_reopens_breaker() -> None:
    clock = FakeClock()
    gatekeeper = _make_gatekeeper(clock, breaker_cooldown_seconds=5.0)
    _trip_breaker(gatekeeper)

    clock.advance(5.0)
    gatekeeper.acquire()
    gatekeeper.release(outcome="retryable_error")

    assert gatekeeper.snapshot()["breaker_state"] == "OPEN"


def test_acquire_timeout_when_concurrency_slot_unavailable() -> None:
    clock = FakeClock()
    gatekeeper = _make_gatekeeper(clock, max_concurrency=1)
    gatekeeper.acquire()

    with pytest.raises(GatekeeperTimeoutError):
        gatekeeper.acquire(timeout=0.0)


def test_gate_context_manager_records_success_and_releases() -> None:
    clock = FakeClock()
    gatekeeper = _make_gatekeeper(clock)

    with gatekeeper.gate() as recorder:
        assert gatekeeper.snapshot()["in_flight"] == 1
        recorder.record("success")

    snapshot = gatekeeper.snapshot()
    assert snapshot["in_flight"] == 0
    assert snapshot["breaker_state"] == "CLOSED"


def test_gate_context_manager_releases_after_body_exception() -> None:
    clock = FakeClock()
    gatekeeper = _make_gatekeeper(clock)

    with pytest.raises(RuntimeError, match="boom"), gatekeeper.gate():
        raise RuntimeError("boom")

    assert gatekeeper.snapshot()["in_flight"] == 0


def test_snapshot_returns_json_serializable_state() -> None:
    clock = FakeClock()
    gatekeeper = _make_gatekeeper(clock)
    _trip_breaker(gatekeeper)

    snapshot = gatekeeper.snapshot()

    json.dumps(snapshot)
    assert snapshot["breaker_state"] == "OPEN"
    assert set(snapshot) == {
        "rpm_tokens",
        "rpd_remaining",
        "rpd_resets_at",
        "in_flight",
        "max_concurrency",
        "breaker_state",
        "consecutive_failures",
        "breaker_opened_at",
    }
