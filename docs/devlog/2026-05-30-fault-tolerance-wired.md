# 2026-05-30 — Fault-tolerance wiring: quality gate (C4)

Covers TODO_fault_tolerance.md §F (quality gates F1–F9).

## What was wired (C1–C3)

- **Referee** (`services/referee/server.py`, `apps/referee_app.py`): `ShutdownCoordinator` +
  `install_signal_handlers` in `referee_app.main`; `WatchdogThread` registered per connected
  player in `on_connect`; `HeartbeatSender` started per player; watchdog feeds on every
  received frame in `_turn_runner`.
- **Player** (`services/player/client.py`, `services/player/agent.py`, `apps/player_app.py`):
  `ShutdownCoordinator` + `install_signal_handlers` in `player_app.main`; `WatchdogThread`
  watching the referee; `HeartbeatSender` toward the referee; `GAME_OVER`/`ERROR` converted to
  `coordinator.request_shutdown(...)`.

## Gates run

### Ruff (changed files)

```
uv run ruff check src/agent_arena/shared/shutdown.py src/agent_arena/shared/watchdog.py
  src/agent_arena/shared/heartbeat.py src/agent_arena/services/referee/server.py
  src/agent_arena/apps/referee_app.py src/agent_arena/services/player/client.py
  src/agent_arena/services/player/agent.py src/agent_arena/apps/player_app.py
```

Result: **All checks passed!** (0 violations)

### Full test suite

```
uv run pytest -q
```

Result: **289 passed** in 21.81 s — **91.23% total coverage** (≥ 85% gate passed).

### Shared-module coverage (fault-tolerance files)

```
uv run pytest tests/unit/shared --cov=agent_arena --cov-report=term-missing -q
```

Key fault-tolerance module coverage (from the run above):

| Module | Coverage |
|---|---|
| `shared/shutdown.py` | 92% |
| `shared/watchdog.py` | 100% |
| `shared/heartbeat.py` | 100% |
| `shared/api_gatekeeper.py` | 98% |
| `shared/config.py` | 93% |

All three fault-tolerance modules exceed the 85% threshold (FT-AC7). The overall 31% total
in this targeted run is the known coverage-trap artifact (the global `--cov=agent_arena`
includes all service modules not exercised by the shared-only test subset). The authoritative
gate is the full `uv run pytest -q` above.

## Judgement

**Pass.** Ruff clean on all touched files. Full suite 289/289, 91.23% coverage. All three
fault-tolerance shared modules at ≥ 85% individual coverage. Referee and player are fully
wired with `ShutdownCoordinator`, `WatchdogThread`, and `HeartbeatSender`. Part C complete.
