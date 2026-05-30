# Task Tracking — Game Engine Layer

| Field    | Value                                      |
|----------|--------------------------------------------|
| Document | `TODO_game_engine.md`                      |
| Project  | `agent-arena`                              |
| Version  | 1.00                                       |
| Date     | 2026-05-30                                 |

> Status: `[ ]` not started · `[~]` in progress · `[x]` done
> Every task maps to at least one requirement in [PRD_game_engine.md](PRD_game_engine.md).
> Companion: [PLAN_game_engine.md](PLAN_game_engine.md)

---

## Module A — Engine Contract (`services/game/engine_base.py`)

### A1 — Define `GameEngine` ABC Interface
- [x] **A1.1** Define the abstract base class `GameEngine` with abstract methods: `get_initial_state`, `validate_move`, `apply_move`, `get_legal_moves`, and `is_terminal`.
  - *DoD/Evidence:* `src/agent_arena/services/game/engine_base.py:8-34`

---

## Module B — State Representation (`services/game/debate_state.py`)

### B1 — Define `DebateState` and Components
- [x] **B1.1** Implement frozen dataclasses `DebateState`, `DebateMove`, and `TurnRecord` to represent structured and immutable state snapshots.
  - *DoD/Evidence:* `src/agent_arena/services/game/debate_state.py:17-106`
- [x] **B1.2** Implement JSON serialization and deserialization helpers (`to_dict` / `from_dict`) on state classes.
  - *DoD/Evidence:* `src/agent_arena/services/game/debate_state.py:107-135`

---

## Module C — Debate Rules Implementation (`services/game/debate_engine.py`)

### C1 — Implement `DebateEngine` Logic
- [x] **C1.1** Implement initialization from configuration dictionary containing round, word cap, and speaker rules.
  - *DoD/Evidence:* `src/agent_arena/services/game/debate_engine.py:36-42`
- [x] **C1.2** Implement `get_initial_state()` returning a clean starting state.
  - *DoD/Evidence:* `src/agent_arena/services/game/debate_engine.py:44-53`
- [x] **C1.3** Implement tier-1 mechanical validation of moves (checking type, presence of text, and word limits).
  - *DoD/Evidence:* `src/agent_arena/services/game/debate_engine.py:55-67`
- [x] **C1.4** Implement legal moves descriptor generation per state/turn constraints.
  - *DoD/Evidence:* `src/agent_arena/services/game/debate_engine.py:69-88`
- [x] **C1.5** Implement pure deterministic state transition in `apply_move()` yielding a new state.
  - *DoD/Evidence:* `src/agent_arena/services/game/debate_engine.py:90-134`
- [x] **C1.6** Implement termination condition check `is_terminal()`.
  - *DoD/Evidence:* `src/agent_arena/services/game/debate_engine.py:136-138`

---

## Module D — Referee Integration (`services/referee/`)

### D1 — Integrate Engine with Referee Loop
- [x] **D1.1** Ensure referee game loop and turn runner invoke engine interfaces (`get_legal_moves`, `validate_move`, `apply_move`, `is_terminal`) to drive the game logic.
  - *DoD/Evidence:* `src/agent_arena/services/referee/game_loop.py:80,101` and `src/agent_arena/services/referee/_turn_runner.py:101,143,170`

---

## Module E — Deterministic Replay (Future/Gaps)

### E1 — Replay Mechanism
- [ ] **E1.1** Implement a deterministic replay path that re-runs the game loop using a transcript record and asserts identical state transitions.
  - *DoD/Evidence:* None (Open item/feature gap)

---

## Requirement traceability matrix

| PRD Requirement | Covered by tasks |
|---|---|
| Section 2 (validate_move signature) | Task C1.3 |
| Section 2 (apply_move signature) | Task C1.5 |
| Section 2 (is_terminal signature) | Task C1.6 |
| Section 2 (get_initial_state) | Task C1.2 |
| Section 2 (get_legal_moves) | Task C1.4 |
| Section 2 (JSON-serializable) | Task B1.2 |
| Section 3 (Turn-based / 2-player) | Task C1.1, Task C1.4 |
| Section 3 (Determinism) | Task C1.5 |
| Section 3 (No Network IO) | Module C (Debate Rules Implementation) |
| Section 5 (Edge Case - Out-of-turn Move) | Task D1.1 (enforced by `_turn_runner.py` routing) |
| Section 5 (Edge Case - Invalid Move Content) | Task C1.3 |
| Section 5 (Edge Case - Terminal State) | Task C1.6 |
