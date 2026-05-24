# PRD — Wire Protocol Mechanism

## 1. Purpose
The wire protocol defines the structure, framing, serialization, and sequence of messages exchanged between the Referee and Player programs over TCP. It ensures reliable, version-checked, and typed communications, allowing agents and the game engine to be decoupled from transport logistics.

## 2. Input / Output (I/O) & Structure
Messages are serialized as UTF-8 encoded JSON strings, framed over raw TCP streams using a length-prefix framing protocol.

### 2.1 Framing Format
- **Header**: A 4-byte big-endian integer representing the length of the JSON payload in bytes.
- **Payload**: The JSON-serialized message envelope.

### 2.2 Envelope Schema
Every message envelope MUST contain:
- `protocol_version` (string): Fixed at `"1.00"`.
- `type` (string): One of the defined message types (e.g. `REGISTER`, `GAME_START`).
- `match_id` (string): Unique identifier for the match.
- `sender` (string): Identifier of the sender process.
- `seq` (integer): Sequential message count for debugging/ordering.
- `timestamp` (string): ISO 8601 formatted timestamp.
- `payload` (object): Type-specific parameters.

## 3. Constraints
- **Maximum Frame Size**: 10 MB to prevent out-of-memory attacks.
- **Encoding**: Strict UTF-8.
- **Timeout**: Network operations must respect the configurable connect and read/write timeouts.

## 4. Alternatives Considered
- **WebSockets / HTTP**: Rejected. WebSockets require extra library dependencies. Plain TCP sockets are standard, lightweight, and fully supported in the Python standard library.
- **Protobuf / MessagePack**: Rejected. Binary formats are harder to debug visually in log files. JSON is human-readable, fulfilling NFR4 (Maintainability).

## 5. Success & Edge-Case Tests
- **Success - Happy Path registration**: `REGISTER` -> `REGISTER_ACK` -> `ROLE_ASSIGN` works cleanly.
- **Edge Case - Protocol version mismatch**: A player connects with version `"0.90"`. The referee sends a typed error and closes the connection.
- **Edge Case - Truncated Frame / Partial Read**: A TCP packet splits the frame. The framing reader correctly buffers and waits for the remaining bytes without raising an error.
- **Edge Case - Oversized Frame**: A client sends a frame header declaring 15 MB. The server drops the connection instantly to prevent memory issues.
