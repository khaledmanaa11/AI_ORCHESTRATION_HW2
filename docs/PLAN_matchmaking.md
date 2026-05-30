# Architecture Plan — Matchmaking & Registration Layer

| Field    | Value                                      |
|----------|--------------------------------------------|
| Document | `PLAN_matchmaking.md`                      |
| Project  | `agent-arena`                              |
| Version  | 1.00                                       |
| Date     | 2026-05-30                                 |
| Status   | Approved                                   |

> Companion: [PRD_matchmaking.md](PRD_matchmaking.md) · [TODO_matchmaking.md](TODO_matchmaking.md)
> No source code in this document — structure, interfaces in prose, and diagrams only.

---

## 1. Overview

The Matchmaking and Registration Layer manages player connections, handles the initial handshake, performs version checking, assigns roles, and prepares the game loop configuration. It coordinates the transition from raw connection status to an active game state with exactly two players assigned to their respective sides (`PRO` and `CON`).

```
    Player 1                               Referee                               Player 2
       │                                      │                                     │
       │ Connection 1 (TCP)                   │                                     │
       ├─────────────────────────────────────>│                                     │
       │                                      │                                     │
       │ Message: REGISTER                    │                                     │
       ├─────────────────────────────────────>│                                     │
       │                                      │ Connection 2 (TCP)                  │
       │                                      │<────────────────────────────────────┤
       │                                      │                                     │
       │                                      │ Message: REGISTER                   │
       │                                      │<────────────────────────────────────┤
       │                                      │                                     │
       │                                      │ [Verify version & details]          │
       │                                      │ [Seeded role assignment]            │
       │                                      │                                     │
       │ Message: REGISTER_ACK                │ Message: REGISTER_ACK               │
       │<─────────────────────────────────────┼────────────────────────────────────>│
       │                                      │                                     │
       │ Message: ROLE_ASSIGN (PRO/CON)       │ Message: ROLE_ASSIGN (PRO/CON)      │
       │<─────────────────────────────────────┼────────────────────────────────────>│
       │                                      │                                     │
```

---

## 2. File Structure

Matchmaking modules and connection logic reside in `services/referee/` and `services/player/`.

```
src/agent_arena/
├── services/
│   ├── referee/
│   │   ├── matchmaking.py    ← Seeded side assignment, game config assembly
│   │   └── server.py         ← TCP server, registers players, triggers start or rejects
│   └── player/
│       ├── client.py         ← TcpClient connection, wraps FramedChannel, runs agent
│       └── agent.py          ← Runs registration loop (REGISTER -> ROLE_ASSIGN -> run)
└── shared/
    └── transport/
        └── tcp_server.py     ← Core TcpServer accepting connections and enforcing caps
```

---

## 3. Building Blocks

### 3.1 Side Assignment (`assign_sides`)
- **Signature**: `assign_sides(player_ids: list[str], seed: int) -> dict[str, str]`
- **Functionality**: Returns a dictionary mapping player IDs to their respective sides (`PRO` or `CON`). Uses a seeded random generator for reproducibility.

### 3.2 Game Configuration (`build_game_config`)
- **Signature**: `build_game_config(motion: str, weights: dict[str, int], format_cfg: dict[str, Any], evidence_pack: dict[str, Any]) -> dict[str, Any]`
- **Functionality**: Assembles the identical player-bound configuration dictionary (including the debate rubric, motion, and formats). The `judge_variant` is intentionally excluded as it is referee-private.

### 3.3 Match Setup (`setup_match`)
- **Signature**: `setup_match(...) -> MatchSetup`
- **Functionality**: Packages side maps, game configs, and initial game states, raising `MatchAbortError` on pre-game setup issues.

### 3.4 Referee Connection Handler (`RefereeServer`)
- **Class**: `RefereeServer`
- **Functionality**: Listens for connections. Registers up to two players, and spins up `DebateGameLoop` once the limit is met. Rejects any third player attempt by sending an error before socket closure.

---

## 4. Handshake Sequence

1. **Player Connection & Verification**:
   - Player clients connect and send a `REGISTER` message.
   - The referee checks version compatibility using `validate(envelope, expected_version)`.
2. **Registration Acknowledgment**:
   - On successful validation, the referee replies with `REGISTER_ACK` carrying the newly generated `match_id`.
3. **Role Assignment**:
   - The referee assigns roles (`PRO` / `CON`) via `ROLE_ASSIGN` along with the identical game config dictionary.
4. **Error / Excess Connections**:
   - Any connection attempt after two players are registered is rejected with a `MATCH_FULL` error and disconnected.
   - Version mismatches are greeted with `VERSION_MISMATCH` before closing.

---

## 5. Testing Strategy

- **Unit Tests**:
  - `tests/unit/services/referee/test_matchmaking.py`: Validates configuration assembly, seeded side assignments, and pre-start abort scenarios.
- **Integration Tests**:
  - `tests/integration/test_debate_loop.py`: Ensures the real TCP handshake functions correctly end-to-end, checking that extra connections are handled cleanly.

---

## 6. Architecture Decision Records (ADR)

| ADR | Decision | Rationale | Trade-off |
|-----|----------|-----------|-----------|
| MM-001 | Seeded Side Assignment | Deterministic assignment based on `seed` ensures test reproducibility. | Requires client seeds to be coordinate-bound. |
| MM-002 | Private Judge Config | Excluding `judge_variant` from the player-bound game config prevents side-channel information leaks. | Client cannot inspect the judging strategy. |
| MM-003 | Hard Limit on Players | The matchmaking loop allows exactly 2 players, rejecting others immediately. | Limits multi-player expansion without code change. |
