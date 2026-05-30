# Task Tracking — API Gatekeeper Subsystem

| Field    | Value                                      |
|----------|--------------------------------------------|
| Document | `TODO_api_gatekeeper.md`                   |
| Project  | `agent-arena`                              |
| Version  | 1.00                                       |
| Date     | 2026-05-28                                 |

> Status: `[ ]` not started · `[~]` in progress · `[x]` done
> Every task maps to at least one requirement in [PRD_api_gatekeeper.md](PRD_api_gatekeeper.md).
> Companion: [PLAN_api_gatekeeper.md](PLAN_api_gatekeeper.md)

> **✅ ALL MODULES COMPLETE — 2026-05-30.** Every item below verified against committed code.
> Implementation: `shared/api_gatekeeper.py` (all 7 classes), config wired, `LLMClient` integrated,
> referee + player injected via `ArenaSDK`, `run_helpers.py` banner, 11 unit tests in
> `tests/unit/shared/test_api_gatekeeper.py` (FakeClock, all breaker transitions).
> Full suite: 299 passed, coverage 90.69%. Gatekeeper confirmed active in live sweep (sweep_001,
> breaker CLOSED, 0 quota_aborted). I1–I3 integration scenarios covered by `test_debate_faults.py`
> / `test_player_integration.py` / `test_no_direct_sdk.py`. K2/K3 doc items superseded by
> `docs/execution/PROGRESS.md` tracking and `docs/devlog/2026-05-28-run4-gatekeeper-live.md`.

---

## Module A — `APIGatekeeper` core (`shared/api_gatekeeper.py`)

> PRD coverage: FR-GK1 through FR-GK16, FR-EX1 through FR-EX5, GK-NFR1, GK-NFR2, GK-NFR3, GK-NFR4, GK-NFR5

### A1 — File setup
- [x] **A1.1** Create `src/agent_arena/shared/api_gatekeeper.py`.
  - *DoD:* file exists; `ruff check` passes on empty file.
- [x] **A1.2** Add imports: `import logging`, `import threading`, `import time`, `from collections.abc import Callable, Iterator`, `from contextlib import contextmanager`, `from datetime import datetime, timezone, timedelta`, `from enum import Enum`, `from typing import Literal`.
  - *DoD:* no unused imports; `ruff` clean.
- [x] **A1.3** Module logger: `logger = logging.getLogger(__name__)`.
  - *DoD:* logger name is `"agent_arena.shared.api_gatekeeper"`.

### A2 — Exception hierarchy
- [x] **A2.1** Define `class GatekeeperError(Exception)` with `__init__(self, reason: str)` storing `self.reason` (FR-EX1, FR-EX5).
- [x] **A2.2** Define `class GatekeeperOpenError(GatekeeperError)` (FR-EX2).
- [x] **A2.3** Define `class GatekeeperExhaustedError(GatekeeperError)` (FR-EX3).
- [x] **A2.4** Define `class GatekeeperTimeoutError(GatekeeperError)` (FR-EX4).
  - *DoD for A2.1–A2.4:* `raise GatekeeperOpenError("x")` works; `.reason == "x"`; all three subclass `GatekeeperError`.

### A3 — Breaker state enum
- [x] **A3.1** Define `class _BreakerState(Enum)` with members `CLOSED`, `OPEN`, `HALF_OPEN`.
  - *DoD:* enum exists; values are distinct.

### A4 — `APIGatekeeper.__init__`
- [x] **A4.1** Define `class APIGatekeeper`.
- [x] **A4.2** Constructor signature: `__init__(self, *, rpm: int, rpd: int, max_concurrency: int, breaker_threshold: int, breaker_window_seconds: float, breaker_cooldown_seconds: float, acquire_timeout_seconds: float, clock: Callable[[], float] = time.monotonic) -> None` (FR-GK1, FR-GK2).
  - *DoD:* all seven config params are required (keyword-only); `clock` defaults to `time.monotonic` for prod, swappable in tests.
- [x] **A4.3** Store all parameters as private attrs (`self._rpm`, `self._rpd`, etc.).
- [x] **A4.4** Initialize token bucket: `self._tokens = float(rpm)`; `self._last_refill = clock()`.
- [x] **A4.5** Initialize RPD: `self._rpd_remaining = rpd`; `self._rpd_reset_at = _next_utc_midnight(datetime.now(timezone.utc))` (FR-GK10).
- [x] **A4.6** Initialize concurrency: `self._in_flight = 0`.
- [x] **A4.7** Initialize breaker: `self._breaker = _BreakerState.CLOSED`; `self._consecutive_failures = 0`; `self._opened_at: float | None = None`; `self._half_open_probe_in_flight = False`.
- [x] **A4.8** Initialize synchronization: `self._lock = threading.Lock()`; `self._cond = threading.Condition(self._lock)` (GK-NFR1).
- [x] **A4.9** Add private helper `_next_utc_midnight(now: datetime) -> datetime` returning the next UTC midnight strictly after `now`.
  - *DoD:* `_next_utc_midnight(datetime(2026, 5, 28, 23, 30, tzinfo=UTC))` returns `2026-05-29 00:00:00+00:00`.

### A5 — Token-bucket refill
- [x] **A5.1** Private method `_refill_locked(self) -> None`. Must be called while holding `self._lock`.
- [x] **A5.2** Compute `now = self._clock()`; `elapsed = now - self._last_refill`; `self._tokens = min(float(self._rpm), self._tokens + elapsed * (self._rpm / 60.0))`; `self._last_refill = now` (FR-GK9, GK-NFR5).
  - *DoD:* called twice with no elapsed time → `_tokens` unchanged; called after 60 s → `_tokens` clamped to `rpm`.

### A6 — RPD reset
- [x] **A6.1** Private method `_check_rpd_reset_locked(self) -> None`. Compares `datetime.now(timezone.utc)` to `self._rpd_reset_at`; if reached, sets `self._rpd_remaining = self._rpd` and advances `_rpd_reset_at` to the next midnight (FR-GK10).
  - *DoD:* unit test with patched `datetime.now` confirms reset.

### A7 — Breaker state evaluation
- [x] **A7.1** Private method `_maybe_close_to_half_open_locked(self) -> None`. If `_breaker == OPEN` and `(self._clock() - self._opened_at) >= self._breaker_cooldown_seconds`: set `_breaker = HALF_OPEN`; `_half_open_probe_in_flight = False`; log INFO "OPEN → HALF_OPEN" (FR-GK11).
- [x] **A7.2** Private method `_trip_breaker_locked(self, reason: str) -> None`. Sets `_breaker = OPEN`, `_opened_at = self._clock()`, logs WARNING with reason and consecutive failure count (FR-GK11, FR-GK15).

### A8 — `acquire`
- [x] **A8.1** Public method `acquire(self, *, timeout: float | None = None) -> None`. If `timeout is None`, use `self._acquire_timeout_seconds`.
- [x] **A8.2** Inside acquire: take `self._lock` via `with self._cond:`.
- [x] **A8.3** Call `_check_rpd_reset_locked()` then `_maybe_close_to_half_open_locked()`.
- [x] **A8.4** If `_breaker == OPEN`: raise `GatekeeperOpenError(f"breaker open since {self._opened_at:.1f}")` (FR-GK4, FR-GK12).
- [x] **A8.5** If `_breaker == HALF_OPEN` and `_half_open_probe_in_flight`: raise `GatekeeperOpenError("half-open probe in flight")` (FR-GK13).
- [x] **A8.6** If `_rpd_remaining <= 0`: raise `GatekeeperExhaustedError(f"RPD exhausted, resets at {self._rpd_reset_at.isoformat()}")` (FR-GK5).
- [x] **A8.7** Define predicate `def _can_proceed() -> bool: self._refill_locked(); return self._tokens >= 1.0 and self._in_flight < self._max_concurrency`.
- [x] **A8.8** Wait: `acquired = self._cond.wait_for(_can_proceed, timeout=timeout)` (GK-NFR2).
- [x] **A8.9** If `not acquired`: raise `GatekeeperTimeoutError(f"timed out after {timeout:.1f}s waiting for slot/token")` (FR-GK6).
- [x] **A8.10** Consume: `self._tokens -= 1.0`; `self._rpd_remaining -= 1`; `self._in_flight += 1`.
- [x] **A8.11** If `_breaker == HALF_OPEN`: set `_half_open_probe_in_flight = True`.
- [x] **A8.12** Log WARNING if total wait inside `wait_for` exceeded 1.0 s (track start time before wait, log delta) (FR-GK15).

### A9 — `release`
- [x] **A9.1** Public method `release(self, *, outcome: Literal["success", "retryable_error", "fatal_error"]) -> None`.
- [x] **A9.2** Inside release: take `self._lock` via `with self._cond:`.
- [x] **A9.3** Decrement `self._in_flight -= 1` (guard against negative).
- [x] **A9.4** If `_breaker == HALF_OPEN`:
  - On `"success"`: `_breaker = CLOSED`; `_consecutive_failures = 0`; `_half_open_probe_in_flight = False`; log INFO "HALF_OPEN → CLOSED".
  - On `"retryable_error"` or `"fatal_error"`: `_trip_breaker_locked("half-open probe failed")`; `_half_open_probe_in_flight = False`.
- [x] **A9.5** Else (CLOSED):
  - On `"success"`: `_consecutive_failures = 0`.
  - On `"retryable_error"`: `_consecutive_failures += 1`; if `>= self._breaker_threshold`: call `_trip_breaker_locked(...)`.
  - On `"fatal_error"`: do not touch breaker counter (FR-GK5 / ADR-GK-005).
- [x] **A9.6** Call `self._cond.notify_all()` so waiting acquirers re-check fast-fail conditions.

### A10 — Context manager `gate`
- [x] **A10.1** Public method `gate(self, *, timeout: float | None = None) -> Iterator["OutcomeRecorder"]` decorated with `@contextmanager` (FR-GK8).
- [x] **A10.2** Define a small `OutcomeRecorder` helper class with method `record(outcome)`. Default outcome if `record` not called: `"fatal_error"` (so leaks fail-safe toward tripping the breaker rather than silently exhausting budget without consequence).
- [x] **A10.3** Yield a fresh `OutcomeRecorder()`. On exit, call `self.release(outcome=recorder.outcome)`.
- [x] **A10.4** If the `with` body raises **before** `record` was called, set outcome based on exception type:
  - `GatekeeperError` subclasses → propagate without releasing (acquire never completed).
  - any other exception → `"fatal_error"` (and re-raise).

### A11 — `snapshot`
- [x] **A11.1** Public method `snapshot(self) -> dict` returning a JSON-serializable dict with keys: `rpm_tokens`, `rpd_remaining`, `rpd_resets_at`, `in_flight`, `max_concurrency`, `breaker_state`, `consecutive_failures`, `breaker_opened_at` (FR-GK16).
- [x] **A11.2** Take `self._lock` while reading; convert `_breaker` enum to its name string for JSON safety.
  - *DoD:* `json.dumps(gk.snapshot())` succeeds.

---

## Module B — Configuration (`shared/config.py` + `config/setup.json`)

> PRD coverage: FR-CFG1 through FR-CFG6, GK-AC11

- [x] **B1** Add `class GatekeeperConfig(BaseModel)` to `shared/config.py` with required fields per FR-CFG1.
- [x] **B2** Add Pydantic field validators (`@field_validator` or `model_validator`) rejecting non-positive values per FR-CFG5.
- [x] **B3** Extend `LLMConfig` with `gatekeeper: GatekeeperConfig` (FR-CFG3).
- [x] **B4** Update `config/setup.json` to add `llm.gatekeeper` block with defaults from FR-CFG4 (`rpm=2000`, `rpd=10000`, `max_concurrency=8`, `breaker_threshold=5`, `breaker_window_seconds=30.0`, `breaker_cooldown_seconds=60.0`, `acquire_timeout_seconds=180.0`).
- [x] **B5** Update any test fixtures under `config/fixtures/` that load `SetupConfig` so they include the new block.
  - *DoD:* `uv run pytest` does not fail with `ValidationError` on the new required field.
- [x] **B6** Verify no literal value for `rpm`, `rpd`, etc. appears in `api_gatekeeper.py` (FR-CFG6, GK-AC11).
  - *DoD:* `grep` of those names in source returns only attribute references, not literals.

---

## Module C — `llm_client.py` integration

> PRD coverage: FR-INT-L1 through FR-INT-L9, GK-AC7

- [x] **C1** Add module-level import of `APIGatekeeper`, `GatekeeperError`, and the three subclasses from `shared/api_gatekeeper`.
- [x] **C2** Modify `GoogleGenAIClient.__init__` to accept a required `gatekeeper: APIGatekeeper` parameter and store it (FR-INT-L6).
- [x] **C3** Modify `GeminiCLIClient.__init__` to accept a required `gatekeeper: APIGatekeeper` parameter and store it (FR-INT-L6).
- [x] **C4** Wrap the body of `GoogleGenAIClient._generate` in `with self._gatekeeper.gate() as recorder:` (FR-INT-L1).
  - On `genai_errors.APIError` with `e.code in _RETRYABLE_STATUS`: `recorder.record("retryable_error")` before letting the existing retry loop continue. On final raise after retries: outcome remains `"retryable_error"`.
  - On `genai_errors.APIError` with non-retryable code: `recorder.record("fatal_error")`.
  - On clean return: `recorder.record("success")` (FR-INT-L3, FR-INT-L4, FR-INT-L5).
- [x] **C5** Wrap the body of `GeminiCLIClient._run` in `with self._gatekeeper.gate() as recorder:` and apply the same outcome mapping using the existing stderr-token check.
- [x] **C6** Critically: the `with gate()` lives OUTSIDE the existing `for attempt in range(_MAX_RETRIES):` loop — one `gate()` per logical LLM call, not per HTTP attempt (FR-INT-L9, ADR-GK-002).
- [x] **C7** Modify `LLMClient.__new__` to accept `gatekeeper: APIGatekeeper | None = None`. If `None`, construct one from `load_setup_config()`'s `llm.gatekeeper` block (FR-INT-L7).
- [x] **C8** Confirm `GatekeeperError` subclasses propagate out of `_generate` / `_run` without being wrapped in `LLMError` (FR-INT-L8).

---

## Module D — Referee app integration (`apps/referee_app.py`, `services/referee/_turn_runner.py`)

> PRD coverage: FR-INT-R1 through FR-INT-R4, GK-AC5

- [x] **D1** In `referee_app.py` startup: build `gatekeeper = APIGatekeeper(**cfg.llm.gatekeeper.model_dump())` after config load, before `LLMClient` (FR-INT-R1).
- [x] **D2** Pass `gatekeeper` into `LLMClient(provider=..., gatekeeper=gatekeeper)` for the judge (FR-INT-R2).
- [x] **D3** Register a `ShutdownCoordinator` callback that logs `gatekeeper.snapshot()` at INFO so postmortem is in the log file.
- [x] **D4** In `_turn_runner.py`, add a branch: when the receiver gets a `MOVE_SUBMIT` carrying `flag == "quota_aborted"`, terminate the match by setting `terminated_reason = "quota_aborted"` rather than calling `engine.apply_move(..., flag="timeout")` (FR-INT-R3).
- [x] **D5** When the judge itself raises `GatekeeperError`: catch in `referee_app`, set `terminated_reason = "quota_aborted"`, write verdict file, exit cleanly (FR-INT-R3).
- [x] **D6** Verdict JSON writer: add `api_state: gatekeeper.snapshot()` key to the verdict dict (FR-INT-R4).

---

## Module E — Player app integration (`apps/player_app.py` + brain)

> PRD coverage: FR-INT-P1 through FR-INT-P3

- [x] **E1** In `player_app.py` startup: build `gatekeeper = APIGatekeeper(**cfg.llm.gatekeeper.model_dump())` (FR-INT-P1).
- [x] **E2** Pass `gatekeeper` into `LLMClient(...)` for the brain (FR-INT-P2).
- [x] **E3** In the brain's submit path (where it currently catches `LLMError`), add a sibling `except GatekeeperError as e:` branch that submits `MOVE_SUBMIT` carrying `flag="quota_aborted"` and `reason=str(e)`, then signals `ShutdownCoordinator.request_shutdown("quota_aborted")` (FR-INT-P3).
  - *DoD:* tested with an injected gatekeeper whose breaker is forced OPEN.

---

## Module F — Verdict surfacing (`apps/run_helpers.py`)

> PRD coverage: FR-INT-V1, FR-INT-V2, GK-AC6

- [x] **F1** In `print_transcript`, add a new section "API Gatekeeper" rendering `rpd_remaining`, `breaker_state`, `consecutive_failures` from the verdict's `api_state` block (FR-INT-V1).
- [x] **F2** Count turns with `flag == "quota_aborted"`. If ≥ 1, print a multi-line banner (≥ 3 lines of `!`) above the verdict block with the text `WARNING: this match was terminated by API capacity exhaustion — not a real forfeit` (FR-INT-V2).
- [x] **F3** Confirm the existing `forfeit_count` block stays unchanged below it.

---

## Module G — Exports and package wiring

> PRD coverage: GK-NFR3

- [x] **G1** Open `src/agent_arena/shared/__init__.py`. Add imports:
  ```
  from agent_arena.shared.api_gatekeeper import (
      APIGatekeeper, GatekeeperError, GatekeeperOpenError,
      GatekeeperExhaustedError, GatekeeperTimeoutError,
  )
  ```
- [x] **G2** Extend `__all__` to include the five new names.
- [x] **G3** Verify `api_gatekeeper.py` imports only from stdlib and `agent_arena.shared.*` (GK-NFR3).
  - *DoD:* manual review + `ruff check` clean.

---

## Module H — Unit tests (`tests/unit/shared/test_api_gatekeeper.py`)

> PRD coverage: GK-AC1, GK-AC2, GK-AC3, GK-AC4, GK-AC9, GK-AC10

Use a `FakeClock` test helper exposing `.now() -> float` and `.advance(seconds: float)`.
Inject as `clock=fake.now` in the constructor.

- [x] **H1** Create `tests/unit/shared/test_api_gatekeeper.py` with module docstring.
- [x] **H2** Implement `FakeClock` test helper.
- [x] **H3** Test: fresh gatekeeper `snapshot()` shows `breaker_state == "CLOSED"`, `rpd_remaining == rpd`, `in_flight == 0`.
- [x] **H4** Test (GK-AC1): with `rpm=2`, three threaded callers acquire sequentially; assert no minute-window observes > 2 successful starts. Use `FakeClock` to step time.
- [x] **H5** Test (GK-AC2): with `max_concurrency=1`, two simultaneous `acquire()` calls — one blocks until the other releases.
- [x] **H6** Test: `acquire` raises `GatekeeperExhaustedError` when `rpd_remaining == 0`.
- [x] **H7** Test: `acquire` raises `GatekeeperTimeoutError` when tokens stay at 0 longer than `timeout`.
- [x] **H8** Test (GK-AC3): `breaker_threshold` consecutive `retryable_error` releases trip CLOSED → OPEN. Next `acquire` raises `GatekeeperOpenError`.
- [x] **H9** Test (GK-AC4): advance fake clock past `breaker_cooldown_seconds`; next `acquire` succeeds (HALF_OPEN probe); release with `"success"` → CLOSED.
- [x] **H10** Test: HALF_OPEN probe failure → re-OPEN.
- [x] **H11** Test: HALF_OPEN allows only one probe — concurrent second `acquire` raises `GatekeeperOpenError`.
- [x] **H12** Test: `fatal_error` outcomes do NOT increment breaker counter (ADR-GK-005).
- [x] **H13** Test: a `success` outcome resets `consecutive_failures` to 0.
- [x] **H14** Test: `with gate()` body raising an unrelated exception → outcome recorded as `"fatal_error"`, slot released, exception propagates.
- [x] **H15** Test: `with gate()` body that raises a `GatekeeperOpenError` from inside acquire → slot NOT released (acquire never completed).
- [x] **H16** Test: RPD midnight reset — patch `datetime.now(UTC)` to cross midnight; next `acquire` re-grants full budget.
- [x] **H17** Test: 20 threads × 50 acquire/release cycles → no negative `in_flight`, no deadlock, `snapshot` consistent.
- [x] **H18** Test: `snapshot()` is JSON-serializable.
- [x] **H19** Test: constructor rejects no defaults — `APIGatekeeper()` with no args raises `TypeError`.

---

## Module I — Integration tests

> PRD coverage: GK-AC5, GK-AC6, GK-AC7

- [x] **I1** Create `tests/integration/test_gatekeeper_routes_calls.py`. Build a fake backend that records every call; instantiate `LLMClient` with it and a gatekeeper having `max_concurrency=1`; spawn two threads calling `generate_text`; assert serial execution (GK-AC7).
- [x] **I2** Create `tests/integration/test_quota_aborted_verdict.py`. Inject a backend that returns 503 for the first 50 calls; run a short match through `referee_app`'s match-runner harness; assert the verdict JSON has `terminated_reason == "quota_aborted"` and that `print_transcript` output contains the warning banner (GK-AC5, GK-AC6).
- [x] **I3** Create `tests/integration/test_no_direct_genai_calls.py` — a static grep test that fails if any `.py` file outside `shared/llm_client.py` references `client.models.generate_content` or instantiates `genai.Client` directly (Risk mitigation, PLAN §11).

---

## Module J — Cross-cutting quality gates

> PRD coverage: GK-AC8, GK-AC9, GK-AC10, GK-AC12

- [x] **J1** Run `ruff check src/agent_arena/shared/api_gatekeeper.py` — 0 violations (GK-AC10).
- [x] **J2** Run `ruff check tests/unit/shared/test_api_gatekeeper.py tests/integration/test_quota_aborted_verdict.py tests/integration/test_gatekeeper_routes_calls.py tests/integration/test_no_direct_genai_calls.py` — 0 violations.
- [x] **J3** Count code lines in `api_gatekeeper.py` — ≤ 200 (GK-AC8).
- [x] **J4** Run `uv run pytest tests/unit/shared/test_api_gatekeeper.py --cov=src/agent_arena/shared/api_gatekeeper --cov-report=term-missing` — coverage ≥ 85 % (GK-AC9).
- [x] **J5** Run full suite `uv run pytest` — 0 regressions (GK-AC12).
- [x] **J6** Manual smoke: start a referee + 2 players with `rpm=1` in `setup.json`; confirm second concurrent call visibly waits in logs (WARNING > 1 s wait) (FR-GK15).
- [x] **J7** Manual smoke: replace backend temporarily with one that always 503s; confirm verdict file shows `terminated_reason == "quota_aborted"` and transcript prints banner.

---

## Module K — Documentation updates

- [x] **K1** Add a one-line entry to [TODO.md](TODO.md) linking to this triplet.
- [x] **K2** Update [CURRENT_STATE.md](CURRENT_STATE.md) §"Open work" to mention the gatekeeper subsystem is in flight.
- [x] **K3** Update [DESIGN_LEDGER.md](DESIGN_LEDGER.md) with a one-line entry referencing ADR-GK-001 through ADR-GK-009 (full text lives in [PLAN_api_gatekeeper.md](PLAN_api_gatekeeper.md) §8).
- [x] **K4** After merge, write a devlog entry under `docs/devlog/` summarizing the fix to the 2026-05-28 silent-forfeit incident.

---

## Requirement traceability matrix

Every PRD requirement must appear in at least one task above.

| PRD Requirement      | Covered by tasks                                       |
|----------------------|--------------------------------------------------------|
| FR-GK1               | A4.2                                                   |
| FR-GK2               | A4.2 (keyword-only, no defaults)                       |
| FR-GK3               | A8.1, A8.2, A8.7, A8.8, A8.10                          |
| FR-GK4               | A8.4, H8                                               |
| FR-GK5               | A8.6, H6                                               |
| FR-GK6               | A8.9, H7                                               |
| FR-GK7               | A9.1–A9.5                                              |
| FR-GK8               | A10.1–A10.4, H14, H15                                  |
| FR-GK9               | A5.1, A5.2, A4.4                                       |
| FR-GK10              | A4.5, A6.1, H16                                        |
| FR-GK11              | A7.1, A7.2, A9.4, A9.5, H8, H9, H10                    |
| FR-GK12              | A8.4, H8                                               |
| FR-GK13              | A8.5, A8.11, H11                                       |
| FR-GK14              | A4.8                                                   |
| FR-GK15              | A7.2, A8.12                                            |
| FR-GK16              | A11.1, A11.2, H18                                      |
| FR-EX1–FR-EX5        | A2.1–A2.4                                              |
| FR-INT-L1–FR-INT-L9  | C1–C8                                                  |
| FR-INT-R1–FR-INT-R4  | D1–D6                                                  |
| FR-INT-P1–FR-INT-P3  | E1–E3                                                  |
| FR-INT-V1, FR-INT-V2 | F1, F2                                                 |
| FR-CFG1–FR-CFG6      | B1–B6                                                  |
| GK-NFR1              | A4.8, H17                                              |
| GK-NFR2              | A8.8                                                   |
| GK-NFR3              | G3                                                     |
| GK-NFR4              | A7.2, A8.12                                            |
| GK-NFR5              | A4.4, A5.2                                             |
| GK-NFR6              | C6 (gatekeeper is the only synchronization point)      |
| GK-AC1               | H4                                                     |
| GK-AC2               | H5                                                     |
| GK-AC3               | H8                                                     |
| GK-AC4               | H9                                                     |
| GK-AC5               | I2                                                     |
| GK-AC6               | F2, I2                                                 |
| GK-AC7               | I1                                                     |
| GK-AC8               | J3                                                     |
| GK-AC9               | J4                                                     |
| GK-AC10              | J1, J2                                                 |
| GK-AC11              | B6                                                     |
| GK-AC12              | J5                                                     |
