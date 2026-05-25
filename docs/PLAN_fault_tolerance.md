# Architecture Plan — Fault Tolerance Subsystem

| Field    | Value                                      |
|----------|--------------------------------------------|
| Document | `PLAN_fault_tolerance.md`                  |
| Project  | `agent-arena`                              |
| Version  | 1.00                                       |
| Date     | 2026-05-25                                 |
| Status   | Draft                                      |

> Companion: [PRD_fault_tolerance.md](PRD_fault_tolerance.md) · [TODO_fault_tolerance.md](TODO_fault_tolerance.md)
> No source code in this document — structure, interfaces in prose, and diagrams only.

---

## 1. Overview

Three new modules are added to `shared/`. They are entirely independent of game logic,
transport, and protocol. Any process (referee or player) wires them together at startup.

```
shared/
├── shutdown.py    ← ShutdownCoordinator
├── watchdog.py    ← WatchdogThread
└── heartbeat.py   ← HeartbeatSender
```

They collaborate like this:

```
                  ┌─────────────────────────────────────────────┐
                  │            Any process (referee or player)   │
                  │                                             │
  OS signal  ──► │  ShutdownCoordinator ◄── WatchdogThread      │
  (SIGTERM)       │         │                   ▲               │
                  │         │ fires             │ heartbeat()   │
                  │   callbacks list            │               │
                  │         │           HeartbeatSender         │
                  │         ▼                   │               │
                  │  [close sockets]    [send_fn every N s]     │
                  │  [send GAME_OVER]                           │
                  └─────────────────────────────────────────────┘
```

---

## 2. The Five Layers of Defense

Each layer catches what the previous one misses.

| Layer | Mechanism                    | Catches                                      | Configured by                     |
|-------|------------------------------|----------------------------------------------|-----------------------------------|
| 1     | OS socket timeout            | Any recv() hanging forever                   | `read_timeout_seconds` on socket  |
| 2     | Heartbeat messages           | Silent-but-open connections                  | `heartbeat_interval_seconds`      |
| 3     | WatchdogThread               | Any peer silent > `read_timeout_seconds`     | `read_timeout_seconds`            |
| 4     | Application timeouts         | Move timeout, lobby timeout, connect timeout | `move_timeout_s`, `lobby_timeout_s` |
| 5     | ShutdownCoordinator          | Everything: cascades clean exit              | N/A — always active               |

---

## 3. Building Blocks

### 3.1 `ShutdownCoordinator`

- **Setup:** instantiated once per process at startup; `install_signal_handlers()` called immediately.
- **Input:** `request_shutdown(reason)` from any thread — watchdog callback, socket error handler, signal handler, or normal game-over flow.
- **Output:** runs all registered callbacks in order; sets its internal `threading.Event`.
- **Key invariant:** callbacks run exactly once, even if `request_shutdown` is called concurrently from multiple threads.
- **Used by:** referee main thread, player main thread; both register cleanup callbacks during startup before any threads are spawned.

### 3.2 `WatchdogThread`

- **Setup:** one instance per process. Peers are registered after they connect.
- **Input:** `heartbeat(peer)` called by the I/O thread each time any message arrives from that peer.
- **Output:** calls `on_timeout(peer)` once for any peer silent longer than `timeout_seconds`.
- **Key invariant:** fires once per peer, never repeatedly.
- **Used by:** referee (watches both players), player (watches the referee).

### 3.3 `HeartbeatSender`

- **Setup:** one instance per connection (one per player in the referee; one in the player pointing at the referee).
- **Input:** `interval_seconds` and a `send_fn` closure provided by the caller.
- **Output:** calls `send_fn()` every `interval_seconds` until stopped or shutdown.
- **Key invariant:** never calls `send_fn` after shutdown is requested.
- **Used by:** referee (sends HEARTBEAT to each player), player (sends HEARTBEAT back to referee).

---

## 4. Thread Model

### 4.1 Referee thread map

```
Main thread
  └─ starts WatchdogThread          (daemon, checks every 1 s)
  └─ starts HeartbeatSender × 2     (daemon, one per player)
  └─ starts receiver thread × 2     (one per player connection)
  └─ starts coordinator thread       (game loop)
  └─ waits on coordinator.wait()
       ↑
       ShutdownCoordinator.request_shutdown()
       can be called from any of the above threads
```

### 4.2 Player thread map

```
Main thread
  └─ starts WatchdogThread          (daemon, watches "referee")
  └─ starts HeartbeatSender × 1     (daemon, sends to referee)
  └─ starts receiver thread × 1     (reads from referee socket)
  └─ starts brain worker thread × 1  (runs brain, Phase 2: LLM call)
  └─ waits on coordinator.wait()
       ↑
       ShutdownCoordinator.request_shutdown()
       can be called from any of the above threads
```

### 4.3 Shared-state ownership

| State                        | Owner              | Protected by      |
|------------------------------|--------------------|-------------------|
| `_event` (shutdown flag)     | ShutdownCoordinator | `threading.Event` (atomic) |
| `_callbacks` list            | ShutdownCoordinator | `threading.Lock`  |
| `_last_seen` dict            | WatchdogThread      | `threading.Lock`  |
| `_fired` set                 | WatchdogThread      | `threading.Lock`  |
| `_stop_event` (heartbeat)    | HeartbeatSender     | `threading.Event` (atomic) |

---

## 5. Shutdown Cascade Sequence

### 5.1 Happy path (normal game over)

```
Referee game loop detects terminal state
  → sends GAME_OVER to both players
  → calls coordinator.request_shutdown("game_over")
      → callback 1: GAME_OVER already sent (no-op)
      → callback 2: close both sockets
      → coordinator._event is set
  → main thread unblocks from coordinator.wait()
  → process exits with code 0

Each player receives GAME_OVER
  → calls coordinator.request_shutdown("game_over")
      → callback 1: close socket
      → coordinator._event is set
  → main thread unblocks
  → process exits with code 0
```

### 5.2 Player crash

```
Player A crashes → socket closes
  → Referee receiver thread: recv() raises ConnectionResetError
  → Referee calls coordinator.request_shutdown("player_disconnect:PLAYER_1")
      → callback 1: send GAME_OVER to Player B
      → callback 2: close all sockets
  → Referee exits

Player B receives GAME_OVER
  → calls coordinator.request_shutdown("game_over")
  → Player B exits cleanly
```

### 5.3 Referee crash

```
Referee crashes (unhandled exception) or is killed
  → Player A + Player B: sockets go silent
  → Each player's WatchdogThread fires after read_timeout_seconds (15 s)
      → on_timeout("referee") called
      → calls coordinator.request_shutdown("watchdog:referee_timeout")
          → callback: close socket
  → Each player exits independently, cleanly
```

### 5.4 SIGTERM on any process

```
SIGTERM received
  → signal handler calls coordinator.request_shutdown("signal:SIGTERM")
  → same callback chain as above runs
  → process exits cleanly
  → surviving processes detect disconnect within read_timeout_seconds
```

---

## 6. File Structure

Only the three new files and one updated `__init__.py`:

```
src/agent_arena/shared/
├── __init__.py          ← add re-exports for ShutdownCoordinator, WatchdogThread, HeartbeatSender
├── shutdown.py          ← ShutdownCoordinator  (NEW)
├── watchdog.py          ← WatchdogThread        (NEW)
├── heartbeat.py         ← HeartbeatSender       (NEW)
├── config.py            (existing — unchanged)
├── logging_setup.py     (existing — unchanged)
└── version.py           (existing — unchanged)

tests/unit/shared/
├── test_shutdown.py     (NEW)
├── test_watchdog.py     (NEW)
└── test_heartbeat.py    (NEW)
```

---

## 7. Architecture Decision Records

| ADR    | Decision                                                      | Rationale                                                         | Trade-off                                    |
|--------|---------------------------------------------------------------|-------------------------------------------------------------------|----------------------------------------------|
| FT-001 | One `ShutdownCoordinator` per process, not per thread         | Single authority; prevents double-cleanup races                   | All callbacks share one lock                 |
| FT-002 | Callbacks run synchronously inside `request_shutdown`         | Guarantees cleanup is complete before the caller's thread moves on | Slow callback delays exit; acceptable here  |
| FT-003 | WatchdogThread fires `on_timeout` exactly once per peer       | Prevents callback spam if connection stays open after timeout     | Peer cannot be "re-registered" after timeout |
| FT-004 | HeartbeatSender is given a `send_fn` closure, not a socket    | Decouples heartbeat timing from protocol/transport details        | Caller must construct the closure            |
| FT-005 | Watchdog uses monotonic clock (`time.monotonic`)              | Immune to system-clock adjustments                                | Cannot be used for wall-clock scheduling     |
| FT-006 | All three classes are daemon threads                          | Process can exit even if a thread hangs — OS cleans up            | Callbacks may not complete if main exits first; acceptable because `coordinator.wait()` blocks until callbacks finish |
| FT-007 | No auto-restart of failed processes                           | Out of scope for this project; complexity cost outweighs benefit  | Operator must restart manually                |

---

## 8. Integration Checklist (wiring, not coding)

When the referee or player is being built (Phase 4 / Phase 5), the following wiring
must be done — in this order:

1. Instantiate `ShutdownCoordinator`.
2. Call `coordinator.install_signal_handlers()`.
3. Register all cleanup callbacks (GAME_OVER send + socket close) **before** opening any socket.
4. Instantiate `WatchdogThread(timeout_seconds=config.network.read_timeout_seconds, on_timeout=..., check_interval_seconds=1.0)`.
5. Call `watchdog.start()`.
6. Open the socket / accept connections.
7. For each connected peer, call `watchdog.register(peer_id)`.
8. Instantiate `HeartbeatSender(interval_seconds=config.game.heartbeat_interval_seconds, send_fn=..., shutdown_event=coordinator._event)`.
9. Call `heartbeat_sender.start()`.
10. In every `recv()` callback: call `watchdog.heartbeat(peer_id)`.
11. In every error handler: call `coordinator.request_shutdown(reason)`.
12. Block main thread: `coordinator.wait()`.
