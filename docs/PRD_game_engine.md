# PRD — Pluggable Game Engine Mechanism

## 1. Purpose
The Game Engine mechanism decouples game rules and states from the network orchestration layer. It exposes a unified interface that the Referee uses to validate moves, progress the game state, and detect terminal conditions.

## 2. Input / Output (I/O)
- **Interface**: `GameEngine` abstract base class.
- **Input**:
  - `validate_move(state, move, role)`: Returns boolean or raises detailed validation error.
  - `apply_move(state, move, role)`: Returns the next game state.
  - `check_terminal(state)`: Returns `(is_terminal: bool, winner: role_or_none)`.
  - `get_initial_state()`: Returns the start state.
  - `get_legal_moves(state, role)`: Returns hints/list of legal actions.
- **Outputs/States**: Must be JSON-serializable to match the protocol requirements.

## 3. Constraints
- **Turn-based**: The engine assumes a turn-based paradigm between 2 players.
- **Determinism**: State transitions must be deterministic given the state and the move.
- **No Network IO**: The engine contains only logic and must not execute network requests or database queries.

## 4. Alternatives Considered
- **Monolithic Referee**: Rejected. Inlining game logic in the referee makes it impossible to swap games (e.g. from Tic-Tac-Toe to Chess) without editing the referee's network loop.
- **State Machine on Player Side**: Rejected. Players cannot be trusted to self-moderate; the referee must remain the sole authority on rules.

## 5. Success & Edge-Case Tests
- **Success - Move Application**: Valid move applied, state transitions correctly, active player changes.
- **Edge Case - Out-of-turn Move**: A player submits a move when it is not their turn. The validator rejects the move.
- **Edge Case - Invalid Move Content**: A player submits a move that is out-of-bounds or violates game rules. The validator rejects it, and referee requests a retry or enforces forfeit.
- **Edge Case - Terminal State**: A move resulting in a win/draw is applied. `check_terminal` returns true, prompting the referee to send `GAME_OVER`.
