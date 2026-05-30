# Task Tracking — Matchmaking & Registration Layer

| Field    | Value                                      |
|----------|--------------------------------------------|
| Document | `TODO_matchmaking.md`                       |
| Project  | `agent-arena`                              |
| Version  | 1.00                                       |
| Date     | 2026-05-30                                 |

> Status: `[ ]` not started · `[~]` in progress · `[x]` done
> Every task maps to at least one requirement in [PRD_matchmaking.md](PRD_matchmaking.md).
> Companion: [PLAN_matchmaking.md](PLAN_matchmaking.md)

---

## Module A — Matchmaking Handshake Flow (`services/referee/server.py`, `matchmaking.py`)

### A1 — Implement Registration Handshake
- [x] **A1.1** Accept `REGISTER` as the first message, extract player identity, and progress to `REGISTER_ACK` and `ROLE_ASSIGN` once two players register.
  - *DoD/Evidence:* `src/agent_arena/services/referee/server.py:131-207`

### A2 — Seeded Side Assignment
- [x] **A2.1** Assign sides `PRO` and `CON` deterministically using a randomized seed to ensure reproducible matches.
  - *DoD/Evidence:* `src/agent_arena/services/referee/matchmaking.py:58-68`

### A3 — Dynamic Config Assembly
- [x] **A3.1** Assemble the player-bound `game_config` package dynamically, ensuring `judge_variant` is excluded as a private setting.
  - *DoD/Evidence:* `src/agent_arena/services/referee/matchmaking.py:24-55`

---

## Module B — Protocol Validation & Version Rejection (`services/referee/server.py`)

### B1 — Validate Inbound REGISTER
- [x] **B1.1** Enforce protocol version compatibility checks on inbound `REGISTER` messages, rejecting mismatched clients immediately with `VERSION_MISMATCH` typed error.
  - *DoD/Evidence:* `src/agent_arena/services/referee/server.py:139-144`

---

## Module C — Connection Capacity Limits (`services/referee/server.py`, `shared/transport/tcp_server.py`)

### C1 — Enforce Exact Connection Limits
- [x] **C1.1** Enforce a strict limit of 2 active players before initiating the game loop.
  - *DoD/Evidence:* `src/agent_arena/services/referee/server.py:167-169`

### C2 — Reject Extra Connections with Error
- [x] **C2.1** Reject the third connection attempt and any subsequent attempts, returning a typed `MATCH_FULL` error before closing the connection.
  - *DoD/Evidence:* `src/agent_arena/services/referee/server.py:127-130`

---

## Module D — Edge-Case Recovery

### D1 — Pre-registration Disconnect Recovery
- [x] **D1.1** Implement timeout and removal logic to handle the pre-registration disconnect of a player (i.e. Player A registers but disconnects before Player B connects) without hanging or shutting down the server.
  - *Status:* ✅ Done. Two mechanisms combined: (1) `recv_timed(framed_ch, config.network.read_timeout_seconds)` at `server.py:134` closes the connection if the registration message never arrives; (2) `WatchdogThread` started at server init (`server.py:65–74`) with `_on_watchdog_timeout → coordinator.request_shutdown(…)` handles a registered player going silent before the match starts — heartbeat is fed on every recv (`server.py:163`). Server never hangs. Commits `fcc3e35`, `bd294ec`.

---

## Requirement traceability matrix

| PRD Requirement | Covered by tasks |
|---|---|
| Section 2 (Input: REGISTER version, ID) | Module B (Validate Inbound REGISTER) |
| Section 2 (Output: ROLE_ASSIGN PRO/CON) | Module A (Seeded Side Assignment) |
| Section 3 (Player Limit: Exactly 2 players) | Module C (Enforce Exact Connection Limits) |
| Section 3 (Third Connection rejected with ERROR) | Module C (Reject Extra Connections with Error) |
| Section 3 (Handshake Order: REGISTER first) | Module A (Implement Registration Handshake) |
| Section 3 (Protocol Version Match) | Module B (Validate Inbound REGISTER) |
| Section 5 (Success - Happy Path match start) | Module A (Implement Registration Handshake) |
| Section 5 (Edge Case - Third Connection) | Module C (Reject Extra Connections with Error) |
| Section 5 (Edge Case - Pre-registration Disconnect) | Module D (Pre-registration Disconnect Recovery) |
