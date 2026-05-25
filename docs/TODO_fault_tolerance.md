# Task Tracking — Fault Tolerance Subsystem

| Field    | Value                                      |
|----------|--------------------------------------------|
| Document | `TODO_fault_tolerance.md`                  |
| Project  | `agent-arena`                              |
| Version  | 1.00                                       |
| Date     | 2026-05-25                                 |

> Status: `[ ]` not started · `[~]` in progress · `[x]` done
> Every task maps to at least one requirement in [PRD_fault_tolerance.md](PRD_fault_tolerance.md).
> Companion: [PLAN_fault_tolerance.md](PLAN_fault_tolerance.md)

---

## Module A — `ShutdownCoordinator` (`shared/shutdown.py`)

> PRD coverage: FR-SC1 through FR-SC10, FT-NFR1, FT-NFR4, FT-NFR5, FT-NFR6

### A1 — File setup
- [x] **A1.1** Create the file `src/agent_arena/shared/shutdown.py`.
  - *DoD:* file exists; `ruff check` passes on an empty file.
- [x] **A1.2** Add imports at the top: `import logging`, `import signal`, `import sys`, `import threading`, `from collections.abc import Callable`.
  - *DoD:* no unused imports; `ruff` clean.
- [x] **A1.3** Create a module-level logger: `logger = logging.getLogger(__name__)`.
  - *DoD:* logger name is `"agent_arena.shared.shutdown"`.

### A2 — Class skeleton
- [x] **A2.1** Define class `ShutdownCoordinator` with a docstring: *"Single authority for process-level shutdown. Thread-safe. Callbacks run exactly once."*
  - *DoD:* class exists and is importable.
- [x] **A2.2** Write `__init__(self) -> None`. Create `self._event = threading.Event()`.
  - *DoD:* `coord = ShutdownCoordinator(); coord.is_shutdown()` returns `False`.
- [x] **A2.3** Inside `__init__`, create `self._callbacks: list[Callable[[], None]] = []`.
  - *DoD:* attribute exists and is an empty list on a fresh instance.
- [x] **A2.4** Inside `__init__`, create `self._lock = threading.Lock()` to protect both `_callbacks` and the one-shot logic.
  - *DoD:* attribute exists.

### A3 — `register_callback`
- [x] **A3.1** Implement `register_callback(self, fn: Callable[[], None]) -> None`. Append `fn` to `self._callbacks` under the lock.
  - *DoD:* a callback registered before `request_shutdown` is called during shutdown.
- [x] **A3.2** Verify that callbacks are stored in insertion order (Python list preserves order).
  - *DoD:* two callbacks registered in order A then B run in order A then B.

### A4 — `request_shutdown`
- [x] **A4.1** Implement `request_shutdown(self, reason: str) -> None`.
  - *DoD:* method exists and is callable.
- [x] **A4.2** Inside `request_shutdown`: acquire `_lock`. Check `self._event.is_set()`. If already set, release lock and return immediately (idempotent — FR-SC10).
  - *DoD:* calling `request_shutdown` twice only runs callbacks once.
- [x] **A4.3** Inside `request_shutdown`: call `self._event.set()` while holding the lock, then release the lock.
  - *DoD:* `is_shutdown()` returns `True` after the first call.
- [x] **A4.4** After releasing the lock, log the reason: `logger.warning("Shutdown requested: %s", reason)` (FR-SC2).
  - *DoD:* a WARNING log entry appears when `request_shutdown` is called.
- [x] **A4.5** After logging, iterate over `self._callbacks` and call each one inside its own `try/except Exception`. On exception, log the traceback at ERROR level and continue to the next callback (FR-SC4).
  - *DoD:* a callback that raises does not prevent subsequent callbacks from running.
- [x] **A4.6** Make a copy of `self._callbacks` before iterating (e.g. `list(self._callbacks)`) to avoid holding the lock during callback execution.
  - *DoD:* callbacks can call `register_callback` without deadlocking.

### A5 — `is_shutdown` and `wait`
- [x] **A5.1** Implement `is_shutdown(self) -> bool`: return `self._event.is_set()` (FR-SC5).
  - *DoD:* returns `False` before shutdown, `True` after.
- [x] **A5.2** Implement `wait(self, timeout: float | None = None) -> bool`: return `self._event.wait(timeout)` (FR-SC6).
  - *DoD:* blocks until shutdown, then unblocks; returns `True` if shutdown, `False` on timeout.

### A6 — Signal handlers
- [x] **A6.1** Implement `install_signal_handlers(self) -> None` (FR-SC7).
  - *DoD:* method exists and is callable.
- [x] **A6.2** Inside `install_signal_handlers`, register a handler for `signal.SIGTERM` that calls `self.request_shutdown("signal:SIGTERM")` (FR-SC8).
  - *DoD:* SIGTERM triggers shutdown on POSIX systems.
- [x] **A6.3** Inside `install_signal_handlers`, register a handler for `signal.SIGINT` that calls `self.request_shutdown("signal:SIGINT")` (FR-SC8).
  - *DoD:* Ctrl+C triggers shutdown.
- [x] **A6.4** On Windows, `signal.SIGTERM` may not be reliably delivered. Wrap the `SIGTERM` registration in a `try/except OSError` and log a warning if it fails — do not crash.
  - *DoD:* `install_signal_handlers()` succeeds on Windows without raising.

### A7 — Unit tests for `ShutdownCoordinator`
- [x] **A7.1** Create `tests/unit/shared/test_shutdown.py`. Add a module docstring.
  - *DoD:* file exists; `pytest` collects it with 0 errors.
- [x] **A7.2** Import `ShutdownCoordinator` from `agent_arena.shared.shutdown`.
  - *DoD:* import succeeds.
- [x] **A7.3** Test `is_shutdown()` returns `False` on a fresh instance.
  - *DoD:* assertion passes.
- [x] **A7.4** Test `is_shutdown()` returns `True` after `request_shutdown("test")`.
  - *DoD:* assertion passes.
- [x] **A7.5** Test that a registered callback is called when `request_shutdown` is called.
  - *DoD:* use a `mock.MagicMock` as the callback; assert `called` is `True`.
- [x] **A7.6** Test that two callbacks registered in order A, B are called in order A then B.
  - *DoD:* use a `call_order` list; append callback names; assert `call_order == ["A", "B"]`.
- [x] **A7.7** Test idempotency: call `request_shutdown` twice; assert callbacks are called exactly once.
  - *DoD:* `mock_callback.call_count == 1`.
- [x] **A7.8** Test that a callback raising `RuntimeError` does not prevent the next callback from running.
  - *DoD:* callback B is still called even though callback A raised.
- [x] **A7.9** Test `wait(timeout=0.0)` returns `False` before shutdown.
  - *DoD:* returns immediately with `False`.
- [x] **A7.10** Test `wait(timeout=1.0)` returns `True` when shutdown is triggered from another thread before the timeout.
  - *DoD:* use `threading.Thread` to call `request_shutdown` after 0.05 s; assert `wait` returns `True`.
- [x] **A7.11** Test thread safety: 10 threads call `request_shutdown` simultaneously; assert callbacks run exactly once.
  - *DoD:* `call_count == 1` after joining all threads.
- [x] **A7.12** Test that a callback registered after `request_shutdown` is NOT called (shutdown already happened).
  - *DoD:* late-registered callback's `call_count == 0`.

---

## Module B — `WatchdogThread` (`shared/watchdog.py`)

> PRD coverage: FR-WD1 through FR-WD11, FT-NFR1, FT-NFR2, FT-NFR3

### B1 — File setup
- [x] **B1.1** Create `src/agent_arena/shared/watchdog.py`.
  - *DoD:* file exists; `ruff` clean.
- [x] **B1.2** Add imports: `import logging`, `import threading`, `import time`, `from collections.abc import Callable`.
  - *DoD:* no unused imports.
- [x] **B1.3** Create module-level logger: `logger = logging.getLogger(__name__)`.
  - *DoD:* logger name is `"agent_arena.shared.watchdog"`.

### B2 — Class skeleton
- [x] **B2.1** Define `class WatchdogThread(threading.Thread)`.
  - *DoD:* class exists and is importable.
- [x] **B2.2** Write `__init__(self, timeout_seconds: float, on_timeout: Callable[[str], None], check_interval_seconds: float = 1.0) -> None` (FR-WD1, FR-WD2).
  - *DoD:* constructor accepts the three parameters.
- [x] **B2.3** Inside `__init__`, call `super().__init__(daemon=True, name="watchdog")` (FR-WD1).
  - *DoD:* `wd.daemon is True`; `wd.name == "watchdog"`.
- [x] **B2.4** Inside `__init__`, store: `self._timeout = timeout_seconds`, `self._on_timeout = on_timeout`, `self._check_interval = check_interval_seconds`.
  - *DoD:* attributes exist.
- [x] **B2.5** Inside `__init__`, create `self._last_seen: dict[str, float] = {}`.
  - *DoD:* empty dict on fresh instance.
- [x] **B2.6** Inside `__init__`, create `self._fired: set[str] = set()` to track which peers have already timed out (FR-WD7).
  - *DoD:* empty set on fresh instance.
- [x] **B2.7** Inside `__init__`, create `self._lock = threading.Lock()` to guard `_last_seen` and `_fired`.
  - *DoD:* attribute exists.
- [x] **B2.8** Inside `__init__`, create `self._stop_event = threading.Event()` (FR-WD8).
  - *DoD:* attribute exists; not set by default.

### B3 — `register`
- [x] **B3.1** Implement `register(self, peer: str) -> None`: acquire lock, set `self._last_seen[peer] = time.monotonic()`, release lock (FR-WD3).
  - *DoD:* after `register("p1")`, `"p1"` appears in `_last_seen`.
- [x] **B3.2** Verify that registering the same peer twice resets its timestamp (no error, no duplicate key in dict).
  - *DoD:* second `register("p1")` updates the timestamp without raising.

### B4 — `heartbeat`
- [x] **B4.1** Implement `heartbeat(self, peer: str) -> None`: acquire lock, update `self._last_seen[peer] = time.monotonic()`, release lock (FR-WD4).
  - *DoD:* calling `heartbeat` updates the stored timestamp.
- [x] **B4.2** If `peer` is not in `_last_seen`, do nothing (silently ignore — FR-WD11).
  - *DoD:* `heartbeat("unknown")` does not raise `KeyError`.

### B5 — `stop`
- [x] **B5.1** Implement `stop(self) -> None`: call `self._stop_event.set()` (FR-WD8).
  - *DoD:* after `stop()`, `_stop_event.is_set()` is `True`.

### B6 — `run`
- [x] **B6.1** Implement `run(self) -> None` (FR-WD5).
  - *DoD:* method exists.
- [x] **B6.2** Inside `run`, loop with `while not self._stop_event.wait(self._check_interval):` — no busy-waiting (FT-NFR2).
  - *DoD:* thread does not spin; CPU usage is near zero while waiting.
- [x] **B6.3** Inside the loop, capture the current time: `now = time.monotonic()` (FT-005 from PLAN — monotonic clock).
  - *DoD:* uses `time.monotonic`, not `time.time`.
- [x] **B6.4** Under the lock, copy the current snapshot: `snapshot = list(self._last_seen.items())`. Release the lock before the next step (FR-WD9).
  - *DoD:* lock is not held during callback execution.
- [x] **B6.5** Iterate over the snapshot. For each `(peer, last_seen_time)`: compute `elapsed = now - last_seen_time`.
  - *DoD:* elapsed is a non-negative float.
- [x] **B6.6** If `elapsed > self._timeout` and `peer` not in `self._fired`: log a WARNING, add `peer` to `self._fired`, call `self._on_timeout(peer)` (FR-WD6, FR-WD7).
  - *DoD:* callback fires exactly once for a timed-out peer.
- [x] **B6.7** Wrap `self._on_timeout(peer)` in `try/except Exception` and log errors — a bad callback must not crash the watchdog.
  - *DoD:* watchdog continues running even if `on_timeout` raises.
- [x] **B6.8** Log a DEBUG message each iteration showing how many peers are being watched.
  - *DoD:* log entry appears at DEBUG level each check cycle.

### B7 — Unit tests for `WatchdogThread`
- [x] **B7.1** Create `tests/unit/shared/test_watchdog.py`.
  - *DoD:* file exists; collected by pytest.
- [x] **B7.2** Import `WatchdogThread` from `agent_arena.shared.watchdog`.
  - *DoD:* import succeeds.
- [x] **B7.3** Test: register a peer, immediately call `heartbeat`, wait `check_interval`, confirm `on_timeout` was NOT called.
  - *DoD:* `mock_callback.call_count == 0`.
- [x] **B7.4** Test: register a peer, do NOT call `heartbeat`, wait `timeout + check_interval + 0.1 s` — confirm `on_timeout` was called with the correct peer name.
  - *DoD:* use a short `timeout_seconds=0.2` for fast tests; `mock_callback.assert_called_once_with("p1")`.
- [x] **B7.5** Test: timeout fires exactly once — wait three check cycles after timeout; confirm callback called only once (FR-WD7).
  - *DoD:* `mock_callback.call_count == 1`.
- [x] **B7.6** Test: repeated `heartbeat` calls reset the timer — send heartbeats every `check_interval / 2` for 3 cycles, confirm no timeout.
  - *DoD:* `mock_callback.call_count == 0` after the heartbeat period.
- [x] **B7.7** Test: `stop()` prevents callback from firing — register a peer, call `stop()` before timeout, wait past timeout, confirm callback not called.
  - *DoD:* `mock_callback.call_count == 0`.
- [x] **B7.8** Test: two peers — only the one without heartbeats times out; the other does not.
  - *DoD:* callback called once for `"p1"`, zero times for `"p2"` (which received heartbeats).
- [x] **B7.9** Test: `heartbeat` for an unregistered peer does not raise (FR-WD11).
  - *DoD:* `wd.heartbeat("ghost")` completes without exception.
- [x] **B7.10** Test: concurrent `heartbeat` calls from multiple threads do not corrupt the `_last_seen` dict.
  - *DoD:* spawn 20 threads each calling `heartbeat("p1")` 100 times; no exception raised; `_last_seen["p1"]` is a valid float.
- [x] **B7.11** Test: `on_timeout` raising an exception does not crash the watchdog thread.
  - *DoD:* watchdog thread is still alive after a raising `on_timeout`.

---

## Module C — `HeartbeatSender` (`shared/heartbeat.py`)

> PRD coverage: FR-HB1 through FR-HB7, FT-NFR2, FT-NFR3

### C1 — File setup
- [x] **C1.1** Create `src/agent_arena/shared/heartbeat.py`.
  - *DoD:* file exists; `ruff` clean.
- [x] **C1.2** Add imports: `import logging`, `import threading`, `from collections.abc import Callable`.
  - *DoD:* no unused imports.
- [x] **C1.3** Create module-level logger: `logger = logging.getLogger(__name__)`.
  - *DoD:* logger name is `"agent_arena.shared.heartbeat"`.

### C2 — Class skeleton
- [x] **C2.1** Define `class HeartbeatSender(threading.Thread)`.
  - *DoD:* class exists and is importable.
- [x] **C2.2** Write `__init__(self, interval_seconds: float, send_fn: Callable[[], None], shutdown_event: threading.Event) -> None` (FR-HB1, FR-HB2).
  - *DoD:* constructor accepts exactly those three parameters.
- [x] **C2.3** Inside `__init__`, call `super().__init__(daemon=True, name="heartbeat-sender")` (FR-HB1).
  - *DoD:* `hs.daemon is True`; `hs.name == "heartbeat-sender"`.
- [x] **C2.4** Inside `__init__`, store: `self._interval = interval_seconds`, `self._send_fn = send_fn`, `self._shutdown_event = shutdown_event`.
  - *DoD:* attributes exist.
- [x] **C2.5** Inside `__init__`, create `self._stop_event = threading.Event()` (FR-HB6).
  - *DoD:* attribute exists; not set by default.

### C3 — `stop`
- [x] **C3.1** Implement `stop(self) -> None`: call `self._stop_event.set()` (FR-HB6).
  - *DoD:* after `stop()`, `_stop_event.is_set()` is `True`.

### C4 — `run`
- [x] **C4.1** Implement `run(self) -> None` (FR-HB3).
  - *DoD:* method exists.
- [x] **C4.2** Inside `run`, create a combined check: `def _should_stop() -> bool: return self._stop_event.is_set() or self._shutdown_event.is_set()`.
  - *DoD:* helper function exists; returns `True` if either event is set.
- [x] **C4.3** Loop using `self._stop_event.wait(self._interval)` — this waits up to `interval_seconds` but exits early if `stop()` is called (FR-HB3, FT-NFR2).
  - *DoD:* no busy-waiting; thread sleeps between beats.
- [x] **C4.4** After the wait, check `_should_stop()`. If True, break the loop and return (FR-HB4).
  - *DoD:* `send_fn` is NOT called after `stop()` or shutdown.
- [x] **C4.5** If not stopping, call `self._send_fn()` inside `try/except Exception`.
  - *DoD:* exceptions are caught.
- [x] **C4.6** On exception in `send_fn`, log at ERROR level with the exception message and break the loop (FR-HB5).
  - *DoD:* an error log appears; loop exits; thread terminates.
- [x] **C4.7** Log a DEBUG message each time a heartbeat is sent successfully.
  - *DoD:* DEBUG log entry appears on each successful send.

### C5 — Unit tests for `HeartbeatSender`
- [x] **C5.1** Create `tests/unit/shared/test_heartbeat.py`.
  - *DoD:* file exists; collected by pytest.
- [x] **C5.2** Import `HeartbeatSender` from `agent_arena.shared.heartbeat`.
  - *DoD:* import succeeds.
- [x] **C5.3** Test: `send_fn` is called after `interval_seconds` elapses.
  - *DoD:* use `interval_seconds=0.1`; after 0.25 s, `mock_fn.call_count >= 1`.
- [x] **C5.4** Test: `send_fn` is called approximately N times in N × `interval_seconds`.
  - *DoD:* use `interval_seconds=0.05`; after 0.3 s, `2 <= call_count <= 7` (generous range for CI timing).
- [x] **C5.5** Test: `stop()` prevents further calls to `send_fn`.
  - *DoD:* call `stop()`; wait `2 × interval_seconds`; `call_count` does not increase after stop.
- [x] **C5.6** Test: setting `shutdown_event` stops the sender (FR-HB4).
  - *DoD:* set the `threading.Event` passed in; wait; confirm no more calls to `send_fn`.
- [x] **C5.7** Test: `send_fn` raising `RuntimeError` stops the thread (FR-HB5).
  - *DoD:* pass a `send_fn` that always raises; thread is no longer alive after the error.
- [x] **C5.8** Test: `send_fn` is NOT called immediately on start — it waits one full interval first.
  - *DoD:* check `call_count == 0` immediately after `start()`; check `call_count >= 1` after `interval_seconds + 0.05 s`.

---

## Module D — Exports and package wiring

> PRD coverage: FT-AC7, FT-AC9, FT-NFR4

- [x] **D1** Open `src/agent_arena/shared/__init__.py`. Add imports:
  ```
  from agent_arena.shared.shutdown import ShutdownCoordinator
  from agent_arena.shared.watchdog import WatchdogThread
  from agent_arena.shared.heartbeat import HeartbeatSender
  ```
  - *DoD:* `from agent_arena.shared import ShutdownCoordinator, WatchdogThread, HeartbeatSender` works.
- [x] **D2** Add `__all__` to `shared/__init__.py` listing the three names.
  - *DoD:* `__all__` is defined.
- [x] **D3** Verify no import in `shared/` pulls from `services/` or `apps/` (FT-NFR4).
  - *DoD:* `ruff check` and manual review confirm no upward imports.

---

## Module E — Configuration validation

> PRD coverage: FR-CFG1, FR-CFG2, FR-CFG3, FT-AC8

- [x] **E1** In `shared/watchdog.py`, confirm there is no literal number used for `timeout_seconds`. The class accepts it as a parameter only.
  - *DoD:* `grep -n "[0-9][0-9]*\.0" watchdog.py` returns only `check_interval_seconds=1.0` (the check granularity, not an operational timeout).
- [x] **E2** In `shared/heartbeat.py`, confirm there is no literal number used for `interval_seconds`.
  - *DoD:* `grep` finds no hardcoded interval.
- [x] **E3** Write one test in `tests/unit/shared/test_shutdown.py` that instantiates `ShutdownCoordinator` without a config — confirms it requires no config.
  - *DoD:* `ShutdownCoordinator()` requires zero arguments.
- [x] **E4** Write one test in `tests/unit/shared/test_watchdog.py` that passes `timeout_seconds` explicitly and confirms it is used (not overridden by a default).
  - *DoD:* `WatchdogThread(timeout_seconds=0.2, on_timeout=fn)` times out at ~0.2 s, not at any hardcoded value.

---

## Module F — Cross-cutting quality gates

> PRD coverage: FT-AC7, FT-AC8, FT-AC9, FT-AC10

- [ ] **F1** Run `ruff check src/agent_arena/shared/shutdown.py` — 0 violations.
  - *DoD:* command exits with code 0.
- [ ] **F2** Run `ruff check src/agent_arena/shared/watchdog.py` — 0 violations.
  - *DoD:* command exits with code 0.
- [ ] **F3** Run `ruff check src/agent_arena/shared/heartbeat.py` — 0 violations.
  - *DoD:* command exits with code 0.
- [ ] **F4** Run `ruff check tests/unit/shared/` — 0 violations.
  - *DoD:* command exits with code 0.
- [ ] **F5** Count code lines in `shutdown.py` — must be ≤ 150 (FT-AC9).
  - *DoD:* `wc -l shutdown.py` (excluding blank lines and comments) ≤ 150.
- [ ] **F6** Count code lines in `watchdog.py` — must be ≤ 150.
  - *DoD:* same check.
- [ ] **F7** Count code lines in `heartbeat.py` — must be ≤ 150.
  - *DoD:* same check.
- [ ] **F8** Run `uv run pytest tests/unit/shared/ --cov=src/agent_arena/shared --cov-report=term-missing`.
  - *DoD:* coverage for `shutdown.py`, `watchdog.py`, `heartbeat.py` is each ≥ 85 % (FT-AC7).
- [ ] **F9** Run full test suite `uv run pytest` — confirm 0 regressions in existing tests.
  - *DoD:* all tests that were passing before remain passing.

---

## Module G — Integration smoke test (manual)

> PRD coverage: FT-AC1 through FT-AC6 (failure catalog scenarios 1, 5, 6)

These are manual verification steps, not automated tests. Each maps to a row in the
PRD §9 failure catalog.

- [ ] **G1** *(Scenario 6 — SIGTERM on referee)* Start the referee stub. Press Ctrl+C. Confirm the process logs `"Shutdown requested: signal:SIGINT"` and exits with code 0.
  - *DoD:* no Python traceback; process exits cleanly.
- [ ] **G2** *(Scenario 7 — SIGTERM on player)* Start a player stub with `ShutdownCoordinator` wired. Press Ctrl+C. Confirm clean exit.
  - *DoD:* no Python traceback.
- [ ] **G3** *(Scenario 3 — watchdog timeout)* Instantiate `WatchdogThread` with `timeout_seconds=3.0`. Register peer `"test"`. Do not call `heartbeat`. After 4 s, confirm `on_timeout("test")` was called.
  - *DoD:* confirmed in a short script; matches expectation.
- [ ] **G4** *(Scenario 5 — heartbeat keeps peer alive)* Instantiate `WatchdogThread` with `timeout_seconds=3.0` and `HeartbeatSender` with `interval_seconds=1.0`. Confirm `on_timeout` is NOT called after 5 s.
  - *DoD:* peer stays alive as long as `HeartbeatSender` is running.

---

## Requirement traceability matrix

Every PRD requirement must appear in at least one task above.

| PRD Requirement | Covered by tasks       |
|-----------------|------------------------|
| FR-SC1          | A4.1, A4.3, A7.4       |
| FR-SC2          | A4.4, A7.4             |
| FR-SC3          | A3.1, A7.5, A7.6       |
| FR-SC4          | A4.5, A7.8             |
| FR-SC5          | A5.1, A7.3             |
| FR-SC6          | A5.2, A7.10            |
| FR-SC7          | A6.1, A6.2, A6.3       |
| FR-SC8          | A6.2, A6.3             |
| FR-SC9          | A2.4, A4.6, A7.11      |
| FR-SC10         | A4.2, A7.7             |
| FR-WD1          | B2.2, B2.3             |
| FR-WD2          | B2.2                   |
| FR-WD3          | B3.1                   |
| FR-WD4          | B4.1, B7.10            |
| FR-WD5          | B6.2                   |
| FR-WD6          | B6.6, B7.4             |
| FR-WD7          | B2.6, B6.6, B7.5       |
| FR-WD8          | B2.8, B5.1, B7.7       |
| FR-WD9          | B6.4                   |
| FR-WD10         | B6.1                   |
| FR-WD11         | B4.2, B7.9             |
| FR-HB1          | C2.2, C2.3             |
| FR-HB2          | C2.2                   |
| FR-HB3          | C4.1, C4.3             |
| FR-HB4          | C4.4, C5.6             |
| FR-HB5          | C4.6, C5.7             |
| FR-HB6          | C3.1, C5.5             |
| FR-HB7          | E2                     |
| FR-INT-R1–R10   | G1, G3, G4 (wiring verified in integration) |
| FR-INT-P1–P8    | G2, G3, G4 (wiring verified in integration) |
| FR-CFG1         | E1, E4                 |
| FR-CFG2         | E2                     |
| FR-CFG3         | E1, E2                 |
| FR-CFG4         | E1                     |
| FT-NFR1         | A2.4, B2.7, A7.11, B7.10 |
| FT-NFR2         | B6.2, C4.3             |
| FT-NFR3         | B2.3, C2.3             |
| FT-NFR4         | D3                     |
| FT-NFR5         | A4.4, B6.6, C4.6       |
| FT-NFR6         | A4.5                   |
| FT-AC1–AC6      | G1–G4                  |
| FT-AC7          | F8                     |
| FT-AC8          | E1, E2, E4             |
| FT-AC9          | F5, F6, F7             |
| FT-AC10         | F1, F2, F3             |
