# PRD — Matchmaking & Registration Mechanism

## 1. Purpose
The Matchmaking mechanism manages the initial lifecycle of player connections. It is responsible for checking protocol versions, registering players, assigning unique game roles, and signaling that the game is ready to start.

## 2. Input / Output (I/O)
- **Input**:
  - Connection requests from players over TCP.
  - `REGISTER` messages containing `agent_id` and `protocol_version`.
- **Output**:
  - `REGISTER_ACK` (success or error payload).
  - `ROLE_ASSIGN` containing the assigned role (e.g. `PLAYER_1`, `PLAYER_2` or `X`, `O`) and game config.
  - An active match context with exactly two registered player channels.

## 3. Constraints
- **Player Limit**: Exactly 2 active players. A third client connection must be rejected with an `ERROR` message or immediate socket closure.
- **Handshake Order**: Players must register before receiving any game messages.
- **Protocol Version**: Must match exactly or be compatible (e.g., matching major/minor).

## 4. Alternatives Considered
- **No registration (implicit match start)**: Rejected. We need to verify agent identity and protocol versions to prevent compatibility issues before starting the game loop.
- **Static config assignment**: Assigning roles based on the port they connect to. Rejected. A dynamic registration handshake is more flexible and matches realistic networked multiplayer designs.

## 5. Success & Edge-Case Tests
- **Success - Happy Path match start**: Player A registers, Player B registers. Roles are assigned, and `GAME_START` is sent.
- **Edge Case - Third Connection**: A third player attempts to connect. The referee sends an error message indicating the match is full and closes the socket.
- **Edge Case - Pre-registration Disconnect**: Player A registers, but disconnects before Player B connects. The server removes Player A, logs the event, and waits for new players.
