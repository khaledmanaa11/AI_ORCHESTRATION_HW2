# PRD — Fault Tolerance Subsystem

| Field       | Value                                      |
|-------------|--------------------------------------------|
| Document    | `PRD_fault_tolerance.md`                   |
| Project     | `agent-arena`                              |
| Version     | 1.00                                       |
| Date        | 2026-05-25                                 |
| Status      | Draft — pending approval before development |
| Author      | Khaled                                     |

> Companion documents: [PLAN_fault_tolerance.md](PLAN_fault_tolerance.md) · [TODO_fault_tolerance.md](TODO_fault_tolerance.md)
> Parent plan: [PLAN.md](PLAN.md) · [PRD.md](PRD.md)

---

## 1. Purpose & Scope

This document specifies the fault tolerance subsystem of `agent-arena`. Its sole
responsibility is guaranteeing that **when any of the three OS processes (referee,
player A, player B) fails in any way, every surviving process detects that failure and
shuts down cleanly** — no orphaned processes, no hanging threads, no silent stalls.

This PRD covers exactly three new shared modules:

| Module                      | Class                | Lives in   |
|-----------------------------|----------------------|------------|
| `shared/shutdown.py`        | `ShutdownCoordinator` | `shared/`  |
| `shared/watchdog.py`        | `WatchdogThread`      | `shared/`  |
| `shared/heartbeat.py`       | `HeartbeatSender`     | `shared/`  |

Everything else — game logic, transport, protocol — is out of scope for this document.

---

## 2. Problem Statement

Without fault tolerance, the following failures leave the system in an unrecoverable state:

| Failure                              | Current effect (no fault tolerance)              |
|--------------------------------------|--------------------------------------------------|
| A player process crashes             | Referee stuck; other player waiting forever      |
| A referee process crashes            | Both players waiting forever (orphaned)          |
| A silent network drop (no OS error)  | All three processes freeze indefinitely          |
| SIGTERM / Ctrl+C on any process      | Other processes keep running, unaware            |
| A player brain hangs (Phase 2)       | Referee waits for MOVE_SUBMIT forever            |

The root cause in all cases: **no process independently detects that a peer is gone
and no process has a guaranteed clean shutdown path**.

---

## 3. Goals

| ID     | Goal                                                                                     |
|--------|------------------------------------------------------------------------------------------|
| FT-G1  | No process is ever left running (orphaned) after another process fails                  |
| FT-G2  | Every process shutdown is clean: log the reason, release resources, exit with code 0    |
| FT-G3  | Silent failures are detected within `read_timeout_seconds` (configured, default 15 s)   |
| FT-G4  | The referee **always** notifies every connected player before it exits, on every path   |
| FT-G5  | SIGTERM and SIGINT trigger a clean shutdown on any process                               |
| FT-G6  | All three components are shared (used by both referee and player — zero duplication)    |
| FT-G7  | The fault tolerance layer has no knowledge of game logic or message types               |

---

## 4. Acceptance Criteria

| ID       | Criterion                                                                               | Target |
|----------|-----------------------------------------------------------------------------------------|--------|
| FT-AC1   | Player crash → surviving player receives GAME_OVER and exits within `read_timeout_s`  | Pass   |
| FT-AC2   | Referee crash → both players detect it and exit cleanly within `read_timeout_s`        | Pass   |
| FT-AC3   | Silent frozen socket → watchdog fires within `read_timeout_seconds`                    | Pass   |
| FT-AC4   | SIGTERM or SIGINT on any process → all processes exit cleanly                           | Pass   |
| FT-AC5   | Shutdown handler is called exactly once even if multiple failure triggers fire at once | Pass   |
| FT-AC6   | No thread and no socket is left open after shutdown completes                           | Pass   |
| FT-AC7   | All three modules achieve ≥ 85 % line coverage in tests                                | Pass   |
| FT-AC8   | No timeout value is hardcoded in source — all come from config                          | Pass   |
| FT-AC9   | Each source file is ≤ 150 code lines                                                    | Pass   |
| FT-AC10  | `ruff check` reports 0 violations on all three files                                   | Pass   |

---

## 5. Functional Requirements

### 5.1 `ShutdownCoordinator` (`shared/shutdown.py`)

**Purpose:** single authority for "this process is shutting down." Any thread in the
process can trigger it; all registered cleanup callbacks run exactly once in order.

| ID       | Requirement                                                                                                                       |
|----------|-----------------------------------------------------------------------------------------------------------------------------------|
| FR-SC1   | Expose `request_shutdown(reason: str) -> None`. Sets an internal `threading.Event` exactly once (idempotent).                   |
| FR-SC2   | On `request_shutdown`, log the reason at WARNING level before running any callback.                                              |
| FR-SC3   | Allow registering cleanup callbacks via `register_callback(fn: Callable[[], None]) -> None`. Callbacks run in registration order.|
| FR-SC4   | All registered callbacks must be called even if one raises an exception. Each exception must be caught, logged, and skipped.     |
| FR-SC5   | Expose `is_shutdown() -> bool` — returns True after the first `request_shutdown` call.                                           |
| FR-SC6   | Expose `wait(timeout: float \| None = None) -> bool` — blocks until shutdown is requested or timeout expires; returns is_shutdown.|
| FR-SC7   | Expose `install_signal_handlers() -> None` — registers OS-level handlers for SIGTERM and SIGINT that call `request_shutdown`.    |
| FR-SC8   | Signal handlers must call `request_shutdown("signal:SIGTERM")` or `request_shutdown("signal:SIGINT")` respectively.             |
| FR-SC9   | Thread-safe: `request_shutdown` and `register_callback` may be called from any thread concurrently.                             |
| FR-SC10  | A second call to `request_shutdown` after the first is a no-op: callbacks do NOT run a second time.                             |

---

### 5.2 `WatchdogThread` (`shared/watchdog.py`)

**Purpose:** background daemon thread that monitors a set of named peers. For each peer,
it tracks the last time a message was received from that peer. If the gap exceeds
`timeout_seconds`, it fires a callback — once per peer.

| ID       | Requirement                                                                                                                       |
|----------|-----------------------------------------------------------------------------------------------------------------------------------|
| FR-WD1   | Subclass `threading.Thread`. Set `daemon = True` and `name = "watchdog"` in `__init__`.                                         |
| FR-WD2   | Constructor accepts `timeout_seconds: float`, `on_timeout: Callable[[str], None]`, `check_interval_seconds: float = 1.0`.       |
| FR-WD3   | Expose `register(peer: str) -> None` — adds the peer and sets its last-seen timestamp to the current monotonic time.            |
| FR-WD4   | Expose `heartbeat(peer: str) -> None` — updates the last-seen timestamp for `peer` to now. Thread-safe.                        |
| FR-WD5   | `run()` loops using `self._stop_event.wait(check_interval_seconds)` — no busy-waiting.                                          |
| FR-WD6   | On each iteration, check all registered peers. If `now - last_seen[peer] > timeout_seconds` and not already fired: call `on_timeout(peer)`. |
| FR-WD7   | Once `on_timeout(peer)` has been called for a peer, do not call it again for that peer.                                         |
| FR-WD8   | Expose `stop() -> None` — sets the internal stop event, causing `run()` to exit cleanly.                                        |
| FR-WD9   | Do not hold the internal lock while calling `on_timeout`. Copy the snapshot under the lock, then release before calling.        |
| FR-WD10  | If no peers are registered, `run()` loops harmlessly until `stop()` is called.                                                   |
| FR-WD11  | A peer that has not yet been registered must be silently ignored by `heartbeat`.                                                 |

---

### 5.3 `HeartbeatSender` (`shared/heartbeat.py`)

**Purpose:** daemon thread that periodically calls a caller-supplied function to send a
keepalive message. It has no knowledge of sockets, message formats, or game state.

| ID       | Requirement                                                                                                                       |
|----------|-----------------------------------------------------------------------------------------------------------------------------------|
| FR-HB1   | Subclass `threading.Thread`. Set `daemon = True` and `name = "heartbeat-sender"` in `__init__`.                                 |
| FR-HB2   | Constructor accepts `interval_seconds: float`, `send_fn: Callable[[], None]`, `shutdown_event: threading.Event`.                |
| FR-HB3   | `run()` waits `interval_seconds` using an internal stop event before each call to `send_fn()`.                                  |
| FR-HB4   | Before calling `send_fn()`, check both the internal stop event and `shutdown_event`. If either is set, exit without calling.    |
| FR-HB5   | If `send_fn()` raises any exception, log it at ERROR level and stop the thread (do not retry).                                   |
| FR-HB6   | Expose `stop() -> None` — sets the internal stop event; `run()` exits on the next iteration.                                    |
| FR-HB7   | No hardcoded interval — always use the value supplied at construction.                                                           |

---

## 6. Integration Requirements

### 6.1 Referee process

| ID          | Requirement                                                                                                         |
|-------------|---------------------------------------------------------------------------------------------------------------------|
| FR-INT-R1   | The referee creates one `ShutdownCoordinator` at process startup before any socket is opened.                      |
| FR-INT-R2   | The referee calls `coordinator.install_signal_handlers()` at startup.                                              |
| FR-INT-R3   | The referee registers a shutdown callback that sends `GAME_OVER` to every currently connected player.              |
| FR-INT-R4   | The referee registers a second callback (after R3) that closes all open sockets.                                   |
| FR-INT-R5   | The referee creates one `WatchdogThread`. After each player connects, it calls `watchdog.register(player_id)`.     |
| FR-INT-R6   | Every time the referee receives any message from a player, it calls `watchdog.heartbeat(player_id)`.               |
| FR-INT-R7   | The watchdog's `on_timeout` callback calls `coordinator.request_shutdown("watchdog:player_timeout:{peer}")`.       |
| FR-INT-R8   | The referee creates one `HeartbeatSender` per connected player after registration completes.                       |
| FR-INT-R9   | Each `HeartbeatSender` is passed the coordinator's internal event as `shutdown_event`.                             |
| FR-INT-R10  | The referee's main thread waits on `coordinator.wait()` after starting all sub-threads.                            |

### 6.2 Player process

| ID          | Requirement                                                                                                         |
|-------------|---------------------------------------------------------------------------------------------------------------------|
| FR-INT-P1   | Each player creates one `ShutdownCoordinator` at startup.                                                          |
| FR-INT-P2   | The player calls `coordinator.install_signal_handlers()` at startup.                                               |
| FR-INT-P3   | The player registers a shutdown callback that closes the TCP socket cleanly.                                        |
| FR-INT-P4   | The player creates one `WatchdogThread` with a single peer: `"referee"`.                                           |
| FR-INT-P5   | Every time the player receives any message from the referee, it calls `watchdog.heartbeat("referee")`.             |
| FR-INT-P6   | The watchdog's `on_timeout` callback calls `coordinator.request_shutdown("watchdog:referee_timeout")`.             |
| FR-INT-P7   | When the player receives `GAME_OVER` or `ERROR`, it calls `coordinator.request_shutdown("game_over")`.             |
| FR-INT-P8   | The player's main thread waits on `coordinator.wait()` after the connection thread is started.                     |

---

## 7. Configuration Requirements

| ID       | Requirement                                                                                          |
|----------|------------------------------------------------------------------------------------------------------|
| FR-CFG1  | `WatchdogThread` `timeout_seconds` is sourced from `config.network.read_timeout_seconds`.           |
| FR-CFG2  | `HeartbeatSender` `interval_seconds` is sourced from `config.game.heartbeat_interval_seconds`.      |
| FR-CFG3  | No default timeout value appears in `watchdog.py` or `heartbeat.py` source.                         |
| FR-CFG4  | `check_interval_seconds` for `WatchdogThread` defaults to `1.0` (acceptable hardcoded default — not an operational value). |

---

## 8. Non-Functional Requirements

| ID       | Requirement                                                                                              |
|----------|----------------------------------------------------------------------------------------------------------|
| FT-NFR1  | Thread-safe: all three components may be called from multiple threads simultaneously                    |
| FT-NFR2  | No busy-waiting: use `threading.Event.wait(timeout)` everywhere, never `time.sleep` in a tight loop    |
| FT-NFR3  | All three thread classes set `daemon = True` so they never prevent the process from exiting             |
| FT-NFR4  | No circular imports: `shared/` modules never import from `services/` or `apps/`                        |
| FT-NFR5  | Every shutdown, timeout event, and send error is logged with its reason and level (WARNING or ERROR)    |
| FT-NFR6  | `ShutdownCoordinator` callbacks must complete before `request_shutdown` returns                         |

---

## 9. Exhaustive Failure Catalog

| # | Failure                          | Detected by                          | Referee response                               | Player response                  | Final state    |
|---|----------------------------------|--------------------------------------|------------------------------------------------|----------------------------------|----------------|
| 1 | Player crashes (socket closes)   | Referee: `ConnectionResetError`      | GAME_OVER → surviving player; shutdown         | Receives GAME_OVER; shutdown     | All clean      |
| 2 | Player hangs (silent socket)     | Referee watchdog after 15 s          | GAME_OVER → surviving player; shutdown         | Receives GAME_OVER; shutdown     | All clean      |
| 3 | Player move timeout              | Referee: `move_timeout` expires      | Forfeit → GAME_OVER → both; shutdown           | Receives GAME_OVER; shutdown     | All clean      |
| 4 | Player sends invalid message     | Referee: validation layer            | ERROR → player; GAME_OVER → both; shutdown     | Receives ERROR/GAME_OVER; shutdown | All clean    |
| 5 | Referee crashes (exception)      | Players watchdog after 15 s         | —                                              | Each independently requests shutdown | No orphans  |
| 6 | Referee SIGTERM / Ctrl+C         | Referee signal handler               | GAME_OVER → all players; shutdown              | Receives GAME_OVER; shutdown     | All clean      |
| 7 | Player SIGTERM / Ctrl+C          | Player signal handler                | Detects socket close (see #1)                  | Exits cleanly via coordinator    | All clean      |
| 8 | Lobby timeout (2nd player never arrives) | Referee: `lobby_timeout` timer | ERROR → waiting player; shutdown              | Receives ERROR; shutdown         | All clean      |
| 9 | Player can't connect to referee  | Player: `connect_timeout` + backoff  | —                                              | Exits with log                   | No orphans     |
| 10| Silent network drop              | Watchdog on both sides after 15 s   | GAME_OVER → all; shutdown                      | Independently requests shutdown  | All clean      |

---

## 10. Out of Scope

- Auto-restarting crashed processes (no supervisor or watchdog daemon outside the process)
- Persisting game state across crashes (no crash recovery or replay)
- Multi-machine network partitions (localhost only in Phase 1 & 2)
- Rate-limiting or back-pressure on heartbeats
