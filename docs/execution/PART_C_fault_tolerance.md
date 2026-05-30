# PART C — Fault-tolerance wiring

`ShutdownCoordinator`, `WatchdogThread`, `HeartbeatSender` are fully built and unit-tested in
`shared/`, but **never instantiated** by the referee or player. This part wires them in.
Reference: `REMAINING_WORK.md` §2 (and §5). Do in order (C2 builds on C1).

---

## C1 — Wire fault-tolerance into the referee
**Goal:** Referee installs signal handlers, runs a `ShutdownCoordinator`, registers each
connected player with a `WatchdogThread`, and sends `HEARTBEAT`s via `HeartbeatSender`.
**Read first:**
- `src/agent_arena/shared/shutdown.py` (`ShutdownCoordinator`, `install_signal_handlers`, ≈ 9–51)
- `src/agent_arena/shared/watchdog.py` (`WatchdogThread`, ≈ 9–56)
- `src/agent_arena/shared/heartbeat.py` (`HeartbeatSender`, ≈ 8–39)
- `src/agent_arena/services/referee/server.py` (`__init__`, `on_connect`, `run_game`, ≈ 30–148)
- `src/agent_arena/apps/referee_app.py` (`main`)
- `PLAN_fault_tolerance.md §4.1` (the intended referee thread map)
**Files (scope):** `services/referee/server.py`, `apps/referee_app.py`.
**Do:**
1. In `referee_app.main` (or `RefereeServer.__init__`): create a `ShutdownCoordinator`, call
   `install_signal_handlers(coordinator)`, and block on `coordinator.wait()` for orderly exit.
2. In `RefereeServer.on_connect`: after a player registers, register it with a `WatchdogThread`
   keyed by player id; on watchdog timeout, request shutdown / forfeit that player.
3. Start a `HeartbeatSender` toward each player (per `PLAN_fault_tolerance.md §4.1`).
4. Register a shutdown callback that closes sockets and finalizes the verdict.
**Verify:**
```
uv run ruff check <files-you-changed>
uv run pytest tests/integration/test_debate_faults.py -q
uv run pytest -q
```
**Commit:** `feat(referee): wire ShutdownCoordinator, WatchdogThread, HeartbeatSender`

---

## C2 — Feed the watchdog on every recv
**Goal:** Every message the referee receives from a player resets that player's watchdog, so a
live-but-slow player isn't killed and a truly dead one is.
**Read first:**
- `src/agent_arena/services/referee/_turn_runner.py` (every `recv`/`recv_timed` call site)
- `src/agent_arena/shared/watchdog.py` (`heartbeat(key)` method)
**Files (scope):** `services/referee/_turn_runner.py` (and `server.py` if recv happens there too).
**Do:** At each point the referee successfully receives a frame from a player, call
`watchdog.heartbeat(player_id)`. Thread the watchdog handle in from C1.
**Verify:**
```
uv run ruff check <files-you-changed>
uv run pytest tests/integration/test_debate_faults.py tests/unit/services/referee -q
```
**Commit:** `feat(referee): reset player watchdog on every received frame`

---

## C3 — Wire fault-tolerance into the player
**Goal:** Player installs signal handlers, watches the referee with a `WatchdogThread("referee")`,
sends heartbeats, and converts `GAME_OVER`/`ERROR` into `coordinator.request_shutdown(...)`.
**Read first:**
- `src/agent_arena/services/player/client.py` (`start`)
- `src/agent_arena/services/player/agent.py` (≈ 125–126 — `self.game_over = True` on GAME_OVER)
- `src/agent_arena/shared/{shutdown,watchdog,heartbeat}.py`
- `src/agent_arena/apps/player_app.py`
**Files (scope):** `services/player/client.py`, `services/player/agent.py`, `apps/player_app.py`.
**Do:**
1. Build a `ShutdownCoordinator` + `install_signal_handlers` in `player_app.main`; block on it.
2. Add a `WatchdogThread("referee")`; feed it on every frame received from the referee.
3. Start a `HeartbeatSender` toward the referee.
4. Replace the bare `self.game_over = True` with `coordinator.request_shutdown("game_over")` (keep
   any flag the loop still needs, but the coordinator drives the exit). Do the same on `ERROR`.
**Verify:**
```
uv run ruff check <files-you-changed>
uv run pytest tests/integration/test_player_integration.py tests/unit/services/player -q
```
**Commit:** `feat(player): wire shutdown/watchdog/heartbeat and drive exit via coordinator`

---

## C4 — Fault-tolerance quality gate
**Goal:** Prove the wiring didn't break coverage or lint, and record it (TODO_fault_tolerance F1–F9).
**Read first:** `docs/TODO_fault_tolerance.md` (the F-section quality gates) and `docs/devlog/` for the devlog format.
**Files (scope):** new file `docs/devlog/<today>-fault-tolerance-wired.md` only (no source edits).
**Do:** Run the gates below, paste their output into a short devlog noting coverage % and that
referee+player are now wired. If coverage on `shared/` is below 85%, mark this step BLOCKED.
**Verify:**
```
uv run ruff check <files-you-changed>
uv run pytest -q
uv run pytest tests/unit/shared --cov=agent_arena --cov-report=term-missing -q
```
**Commit:** `docs(devlog): record fault-tolerance wiring + coverage gate`
