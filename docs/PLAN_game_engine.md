# Architecture Plan — Game Engine Layer

| Field    | Value                                      |
|----------|--------------------------------------------|
| Document | `PLAN_game_engine.md`                      |
| Project  | `agent-arena`                              |
| Version  | 1.00                                       |
| Date     | 2026-05-30                                 |
| Status   | Approved                                   |

> Companion: [PRD_game_engine.md](PRD_game_engine.md) · [TODO_game_engine.md](TODO_game_engine.md)
> No source code in this document — structure, interfaces in prose, and diagrams only.

---

## 1. Overview

The Game Engine mechanism decouples specific game rules, state transitions, and validation from the network orchestration and referee layers. It defines a pluggable, deterministic interface that the Referee uses to validate moves, progress turn counts, retrieve valid actions, and check for terminal conditions.

```
┌────────────────────────────────────────┐
│             RefereeServer              │
│       (Manages TCP/Network IO)         │
└───────────────────┬────────────────────┘
                    │
                    │ invokes loop & turn runner
                    ▼
┌────────────────────────────────────────┐
│             Referee Loop               │
│        (game_loop / _turn_runner)      │
└───────────────────┬────────────────────┘
                    │
   is_terminal / validate_move / apply_move
                    │
┌───────────────────▼────────────────────┐
│             GAME ENGINE                │
│    (DebateEngine / DebateState)        │
│   - Stateless/Immutable mechanics      │
│   - No Network, Disk, or LLM access    │
└────────────────────────────────────────┘
```

By ensuring the game engine is entirely deterministic and free of network/disk IO, the same engine code can be used for offline simulation, test-suite validation, or live matches.

---

## 2. File Structure

The game engine and state classes reside in `services/game/`.

```
src/agent_arena/
└── services/
    ├── game/
    │   ├── __init__.py       ← Exposes DebateEngine, DebateState, etc.
    │   ├── engine_base.py    ← Defines the GameEngine abstract base class
    │   ├── debate_engine.py  ← Implements DebateEngine (debate rules)
    │   └── debate_state.py   ← Defines DebateState, DebateMove, TurnRecord
    └── referee/
        ├── game_loop.py      ← Runs the match loop, checking is_terminal
        └── _turn_runner.py   ← Enforces turn limits and validates moves
```

---

## 3. Building Blocks

### 3.1 `GameEngine` Abstract Base Class (`engine_base.py`)
- Defines the required contract for any pluggable game:
  - `get_initial_state()`: Returns the start state before turn 1.
  - `validate_move(state, move)`: Returns `(legal: bool, reason: str | None)`.
  - `apply_move(state, move, **kwargs)`: Returns a new state without mutating the original.
  - `get_legal_moves(state)`: Returns legal actions descriptor.
  - `is_terminal(state)`: Returns a boolean indicating if the game has ended.

### 3.2 `DebateState` and State Representation (`debate_state.py`)
- Frozen dataclasses (`DebateState`, `TurnRecord`, `DebateMove`) that encapsulate the full state of the match, including:
  - Motion / Topic of the debate.
  - Active turn counter and rules snapshot (R rounds, word caps, retry limits).
  - Transcript of past turns (read-only list/tuple of `TurnRecord`s).
  - Overall status (`PENDING`, `IN_PROGRESS`, `COMPLETE`).

### 3.3 `DebateEngine` (`debate_engine.py`)
- Implements the specific rules of the debate:
  - Mechanical word count validation and limits (`word_cap`).
  - Correct phase mapping (`CONSTRUCTIVE`, `REBUTTAL`, `CLOSING`) and active player determination based on the turn number and `first_speaker` choice.
  - Handling of skipped/empty/exhausted turns by generating empty records flagged with `timeout` or `retry_exhausted` while still advancing turn counts.

---

## 4. Move Validation & Execution Flow

### 4.1 Referee & Engine Interaction Loop
For each turn in the match, the referee retrieves instructions from the engine, runs the interaction, and applies the result:

```
  Referee Loop / Turn Runner                    Game Engine
             │                                       │
             │ get_legal_moves(state)                │
             ├──────────────────────────────────────>│
             │ <─────────────────────────────────────┤ [Constraint descriptor]
             │                                       │
             │  (Requests move from active Player)   │
             │  (Receives MOVE_SUBMIT payload)       │
             │                                       │
             │ validate_move(state, move)            │
             ├──────────────────────────────────────>│
             │ <─────────────────────────────────────┤ (legal = True/False)
             │                                       │
             │  (Runs Referee Brain tier-2 check)    │
             │                                       │
             │ apply_move(state, move, tell, flag)   │
             ├──────────────────────────────────────>│
             │ <─────────────────────────────────────┤ [New DebateState]
             │                                       │
```

Note that the **role/turn enforcement** (verifying the correct player submitted the move, and routing to the active player) is handled in `_turn_runner.py` by checking the engine's `get_legal_moves()` and active speaker status, not inside the core game engine validation methods.

---

## 5. Testing Strategy

- **Unit Tests**:
  - `test_debate_state.py`: Confirms state initialization, serialization (`to_dict`/`from_dict`), and immutability.
  - `test_debate_engine.py`: Verifies turn routing, active speaker flip, word cap limits, and transition logic.
  - `test_game_loop.py`: Ensures the referee loop properly queries `is_terminal` and applies moves.
- **Deterministic Replay Test (Pending)**:
  - Mock transcript replay test path to verify that re-applying a historical log yields identical game states.

---

## 6. Architecture Decision Records (ADR)

| ADR | Decision | Rationale | Trade-off |
|-----|----------|-----------|-----------|
| GE-001 | Immutable State | State is represented as frozen/immutable dataclasses; `apply_move` returns a new state. | Prevents state corruption and side effects, though it increases allocations. |
| GE-002 | Separation of Role Routing | Role routing lives in the turn runner; the engine only defines mechanics. | Keeps the engine simple and focused strictly on the rules of the game. |
| GE-003 | Externalized Verdicts | GameEngine returns only a terminal boolean; winner/scoring is delegated to the Referee Brain. | Decouples mathematical winner calculation from rule mechanics. |
