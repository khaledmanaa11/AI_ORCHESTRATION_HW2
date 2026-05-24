# Product Requirements Document (PRD) — Agent Arena

| Field | Value |
|-------|-------|
| Project | `agent-arena` |
| Version | 1.00 |
| Date | 2026-05-24 |
| Status | Draft — pending approval before development |
| Author | Khaled |

> Follows *Guidelines for Writing Professional Software* (Dr. Yoram Segal, V3.00) §2.2 and §20.1.
> Companion documents: [PLAN.md](PLAN.md) · [TODO.md](TODO.md)

---

## 1. Project Overview & Context

### 1.1 Summary
`agent-arena` is a network of **three independent programs (OS processes) that run
simultaneously and communicate with each other over TCP**:

| Agent | Role | Brain |
|-------|------|-------|
| **Referee** | Orchestrator: assigns roles, drives the turn loop, validates moves, declares the result, and makes referee-level decisions | has a Brain |
| **Player A** | Connects to referee, receives its role, plays the game | has a Brain |
| **Player B** | Same as Player A, different role | has a Brain |

The project is delivered in two phases:

- **Phase 1:** a robust, **game-agnostic** orchestration substrate. All three agents run
  with a trivial placeholder brain (no LLM). The focus is the **process model, TCP network,
  and message protocol**.
- **Phase 2:** all three agents are upgraded to **LLM-backed brains** powered by the
  author's Anthropic subscription. The networking layer does not change.

### 1.2 The Problem
Building agents that act as **separate running programs talking to each other** requires a
wire protocol, connection-lifecycle handling, role assignment, turn synchronisation,
timeouts, and graceful crash recovery. Doing this ad hoc produces fragile code that cannot
be upgraded to LLM agents without a rewrite. This project delivers that substrate once,
correctly, so intelligence can be swapped in on top.

### 1.3 Target User
The author: a developer/researcher who wants to run multi-agent, turn-based matches as
independent processes and swap each agent's intelligence freely.

### 1.4 Why three programs, not one
True OS-process isolation means a crashing player cannot corrupt the referee, and the
architecture scales from `localhost` to multiple machines without redesign. See PLAN ADR-001.

---

## 2. Goals, KPIs & Acceptance Criteria

### 2.1 Goals
| ID | Goal |
|----|------|
| G1 | Three processes form a working TCP network, referee as coordination point |
| G2 | Referee assigns each player a distinct role before game start |
| G3 | Full match (start → moves → game over) runs end-to-end |
| G4 | Game rules, referee brain, and player brain are all **pluggable** — Phase 2 requires no transport-layer change |
| G5 | All behaviour is observable (logged) and configurable (no hardcoded values) |

### 2.2 KPIs / Acceptance Criteria
| ID | Criterion | Target |
|----|-----------|--------|
| AC1 | Referee accepts exactly 2 players; rejects a 3rd | Enforced |
| AC2 | Each player receives a unique role before GAME_START | 100 % of matches |
| AC3 | Complete match runs reproducibly on localhost | Pass |
| AC4 | Player disconnect/timeout handled without referee crash | Graceful |
| AC5 | Global test coverage | ≥ 85 % |
| AC6 | `ruff check` violations | 0 |
| AC7 | Every source file | ≤ 150 code lines |
| AC8 | Hardcoded host / port / timeout / key in source | 0 |
| AC9 | Swapping any placeholder brain for an LLM brain | No transport-layer change |

---

## 3. Functional Requirements

### 3.1 Referee
- **FR-R1** Bind and listen on a configurable `host:port`.
- **FR-R2** Accept connections until `player_count` (config) is reached; refuse extras.
- **FR-R3** Registration handshake: agent id/name + protocol-version check.
- **FR-R4** Assign each player a distinct role; send `ROLE_ASSIGN`.
- **FR-R5** Broadcast `GAME_START` with the initial game state.
- **FR-R6** Run the turn loop: request a move, receive it, validate against the pluggable
  rules engine, update state, broadcast `STATE_UPDATE`.
- **FR-R7** Detect terminal states; broadcast `GAME_OVER` with result.
- **FR-R8** Enforce per-move timeout; apply configured violation policy (e.g. forfeit).
- **FR-R9** Log every message sent/received and every state transition.
- **FR-R10** On referee-level decisions (rule interpretation, game-start setup, scenario
  generation) delegate to the **referee brain**; Phase 1 uses a simple placeholder.

### 3.2 Player
- **FR-P1** Connect to referee at configurable `host:port` with retry/backoff.
- **FR-P2** Complete the registration handshake.
- **FR-P3** Receive and store assigned role.
- **FR-P4** On `MOVE_REQUEST`, ask the **player brain** for a decision and submit the move.
- **FR-P5** Apply `STATE_UPDATE` locally; react to `GAME_OVER`.
- **FR-P6** Shut down cleanly on game end or fatal error.

### 3.3 Protocol & Transport
- **FR-T1** A versioned message envelope: `type`, `protocol_version`, `match_id` (null
  until assigned), `sender`, `seq`, `timestamp`, `payload`.
- **FR-T2** A defined set of message types covering the full match lifecycle.
- **FR-T3** Deterministic framing over the TCP byte stream (no partial-read leaks).
- **FR-T4** Rejection of messages with an incompatible protocol version.

### 3.4 LLM Integration (Phase 2)
- **FR-L1** An `LLMBrain` for both referee and each player that satisfies the same brain
  interface as the respective placeholder.
- **FR-L2** LLM brains call the **Anthropic SDK** directly (author's subscription); no
  custom rate-limiting or cost-tracking infrastructure is required for this project.
- **FR-L3** The SDK call is isolated in a shared `LLMCallerMixin` — not duplicated across
  referee and player brains (DRY principle, OOP mixin per guidelines §4.2).

---

## 4. Non-Functional Requirements

| ID | Requirement |
|----|-------------|
| NFR1 | **Reliability** — referee survives player crash/disconnect/timeout; graceful degradation |
| NFR2 | **Security** — no secrets in source; Anthropic key from environment variable only; `.env-example` documents it |
| NFR3 | **Configurability** — all operational values (host, port, timeouts, player count) from config files |
| NFR4 | **Maintainability** — modular building blocks, single responsibility, ≤ 150 lines/file, no code duplication |
| NFR5 | **Testability** — TDD, ≥ 85 % coverage, transport mocked in unit tests |
| NFR6 | **Performance** — match latency dominated by brain decision time, not framework overhead |
| NFR7 | **Portability** — runs on Windows/Linux/macOS via `uv` |

### 4.1 ISO/IEC 25010 mapping
Functional Suitability (full lifecycle), Reliability (fault tolerance), Security (env-var
secrets), Maintainability (modularity, testability), Compatibility (versioned protocol),
Portability (`uv`, no OS-specific assumptions).

---

## 5. User Stories
- **US1** As an operator, I start three processes and watch a complete match in the logs.
- **US2** As a developer, I implement a new game by writing one rules/engine module —
  the network layer is untouched.
- **US3** As a developer, I replace any placeholder brain with an LLM brain and the rest
  of the system continues working.
- **US4** As an operator, I change port/timeout in config without touching code.
- **US5** As a developer, I give the referee an LLM brain so it can make intelligent
  game-management decisions independently of the players.

---

## 6. Assumptions, Dependencies & Constraints

### 6.1 Assumptions
- Phase 1 and Phase 2 run on a single machine (`localhost`); the design must not prevent
  multi-host use later.
- Exactly two players per match (configurable constant).
- Turn-based game: referee mediates all state; players do not talk directly to each other.
- Phase 2 uses the author's Anthropic subscription via the SDK — no production deployment,
  no cost-tracking infrastructure needed.

### 6.2 Dependencies
- Python — managed exclusively via **`uv`**.
- Standard-library `socket` for transport (no broker, no external messaging library).
- `anthropic` Python SDK (Phase 2 only) — auth via `ANTHROPIC_API_KEY` environment variable.

### 6.3 Constraints (from the guidelines)
- SDK-layered architecture; all business logic through one SDK entry point.
- `ruff` clean; ≥ 85 % coverage; files ≤ 150 lines; semantic versioning starting at 1.00.
- `uv` is the only permitted package manager.

---

## 7. Out of Scope (Phase 1)
- Specific rules of any concrete game (a trivial placeholder exercises the loop).
- Graphical UI (CLI/log output only).
- Multi-machine deployment, player authentication, match-history persistence.
- Direct player-to-player communication.
- Rate limiting, token quotas, or cost dashboards.

---

## 8. Timeline & Milestones
| Milestone | Content | Exit criterion |
|-----------|---------|----------------|
| **M0 — Docs** | PRD, PLAN, TODO authored & approved | This document set approved |
| **M1 — Foundation** | config, version, logging, constants | Config loads; version = 1.00 |
| **M2 — Transport** | TCP server/client, framing, Channel | Two processes exchange a framed message |
| **M3 — Protocol** | message types, envelope, payloads, codec, validation | Round-trip + version rejection |
| **M4 — Referee** | matchmaking, game loop, state, brain scaffold | Referee runs loop against stub brains |
| **M5 — Player** | client, agent, placeholder brain | Player completes a full match |
| **M6 — Integration** | referee + 2 players, trivial game | Full match end-to-end on localhost |
| **M7 — Pro phase** | LLM brains for all three agents via SDK | All agents play with LLM brain; no transport change |

> Per the guidelines, each central mechanism requires its own PRD. Tracked in TODO:
> `PRD_protocol.md`, `PRD_matchmaking.md`, `PRD_game_engine.md`, `PRD_referee_brain.md`.
