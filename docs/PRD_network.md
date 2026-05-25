# PRD — Network Layer (Transport + Protocol)

| Field    | Value                                      |
|----------|--------------------------------------------|
| Document | `PRD_network.md`                           |
| Project  | `agent-arena`                              |
| Version  | 1.00                                       |
| Date     | 2026-05-25                                 |
| Status   | Draft — pending approval before development |
| Author   | Khaled                                     |

> Companion documents: [PLAN_network.md](PLAN_network.md) · [TODO_network.md](TODO_network.md)
> Parent plan: [PLAN.md](PLAN.md) · [PRD.md](PRD.md)
> Supersedes the stub in [PRD_protocol.md](PRD_protocol.md) — that file is now retired.

---

## 1. Purpose & Scope

This document specifies the **network layer** of `agent-arena`: the set of modules that
allow the three OS processes (referee, player A, player B) to exchange structured, typed,
version-checked messages over a TCP byte stream.

The network layer has two sub-layers:

| Sub-layer   | Responsibility                                          | Modules                                              |
|-------------|--------------------------------------------------------|------------------------------------------------------|
| **Transport** | Move raw bytes reliably between processes; manage connections | `Channel`, `Framing`, `TcpServer`, `TcpClient`  |
| **Protocol** | Give those bytes meaning; enforce message contracts    | `MessageType`, `Envelope`, `Payloads`, `Codec`, `Validation` |

Everything above this layer (referee logic, player brain, game engine) speaks in typed
message objects and never touches sockets. Everything below it (OS, TCP stack) is opaque.

---

## 2. Problem Statement

Without this layer the three processes cannot exchange any information. Specifically:

| Gap                                           | Effect without this layer                                     |
|-----------------------------------------------|---------------------------------------------------------------|
| No framing over TCP byte stream               | Partial reads; messages bleed into each other                 |
| No typed, versioned message envelope          | Senders and receivers can't agree on what a message means     |
| No version checking                           | An old player silently misinterprets a new referee's messages |
| No payload schema per message type            | Any field can be missing or wrong; errors surface late        |
| No transport abstraction (`Channel`)          | Domain services couple directly to sockets; untestable        |
| No connection lifecycle management            | Referee can't accept exactly N players; players can't retry   |

---

## 3. Goals

| ID     | Goal                                                                                           |
|--------|-----------------------------------------------------------------------------------------------|
| NL-G1  | Two processes can exchange a complete, framed, typed message over a real TCP socket           |
| NL-G2  | A process with the wrong `protocol_version` is rejected before any game logic runs           |
| NL-G3  | The transport layer is fully mockable — domain services never import `socket` directly        |
| NL-G4  | Partial TCP reads are handled invisibly; callers always receive a complete message or an error|
| NL-G5  | All connection and message parameters (port, timeouts, max frame size) come from config       |
| NL-G6  | The codec is lossless: encode → decode round-trips to the original object                    |

---

## 4. Acceptance Criteria

| ID      | Criterion                                                                                  | Target |
|---------|--------------------------------------------------------------------------------------------|--------|
| NL-AC1  | Two in-process Channel instances exchange a HEARTBEAT message round-trip                   | Pass   |
| NL-AC2  | A frame split across two TCP packets is reassembled correctly                              | Pass   |
| NL-AC3  | A frame header declaring > `max_frame_size_bytes` is rejected; connection closed           | Pass   |
| NL-AC4  | A player with `protocol_version = "0.90"` is rejected with a typed ERROR envelope         | Pass   |
| NL-AC5  | An envelope with an unknown `type` is rejected by `Validation`                             | Pass   |
| NL-AC6  | `TcpServer` rejects a third connection attempt while two players are already registered    | Pass   |
| NL-AC7  | `TcpClient` retries connection with exponential backoff on `ConnectionRefusedError`        | Pass   |
| NL-AC8  | All seven modules achieve ≥ 85 % line coverage in unit tests                              | Pass   |
| NL-AC9  | `ruff check` reports 0 violations on all source files                                     | Pass   |
| NL-AC10 | Each source file is ≤ 150 code lines                                                       | Pass   |
| NL-AC11 | No hardcoded port, timeout, or frame-size limit in source — all from config                | Pass   |

---

## 5. Functional Requirements

### 5.1 `Channel` — transport abstraction (`shared/transport/channel.py`)

**Purpose:** decouple domain services from the underlying transport. Any code that sends
or receives messages speaks only `Channel`. The real TCP socket, in-memory pipe for tests,
and any future WebSocket all satisfy the same interface.

| ID        | Requirement                                                                                                          |
|-----------|----------------------------------------------------------------------------------------------------------------------|
| FR-CH1    | Define abstract base class `Channel` with two abstract methods: `send(data: bytes) -> None` and `recv() -> bytes`.  |
| FR-CH2    | `recv()` must raise `ConnectionClosedError` (a project-defined exception) when the peer closes the connection.      |
| FR-CH3    | Provide a concrete `InMemoryChannel` pair: `InMemoryChannel.make_pair()` returns two linked channels for testing.   |
| FR-CH4    | `InMemoryChannel` must be thread-safe: both ends can send/recv concurrently without data corruption.                |
| FR-CH5    | Define `ConnectionClosedError(IOError)` in this module — the single exception type for closed connections.          |

---

### 5.2 `Framing` — length-prefix framing (`shared/transport/framing.py`)

**Purpose:** convert the TCP byte stream (which has no message boundaries) into discrete,
complete message blobs. Uses a 4-byte big-endian unsigned integer header that declares
the payload length.

| ID        | Requirement                                                                                                          |
|-----------|----------------------------------------------------------------------------------------------------------------------|
| FR-FR1    | `send_frame(channel: Channel, data: bytes) -> None` — prepend a 4-byte big-endian length header, then send all bytes. |
| FR-FR2    | `recv_frame(channel: Channel, max_bytes: int) -> bytes` — read the 4-byte header first, then read exactly that many bytes. |
| FR-FR3    | If the declared length exceeds `max_bytes`, raise `FrameTooLargeError` and do NOT attempt to read the payload.      |
| FR-FR4    | Handle partial reads: keep calling `channel.recv()` until the expected byte count is accumulated.                   |
| FR-FR5    | If `channel.recv()` returns empty bytes during a partial read, raise `ConnectionClosedError`.                        |
| FR-FR6    | Define `FrameTooLargeError(IOError)` in this module.                                                                 |
| FR-FR7    | `max_bytes` is always passed by the caller (sourced from config) — no default inside `framing.py`.                  |

---

### 5.3 `TcpServer` — connection acceptor (`shared/transport/tcp_server.py`)

**Purpose:** bind a TCP socket, accept up to `player_count` connections, and hand each
accepted connection to a caller-supplied handler running in its own thread.

| ID        | Requirement                                                                                                          |
|-----------|----------------------------------------------------------------------------------------------------------------------|
| FR-SV1    | `TcpServer(host, port, player_count, on_connect)` — constructor accepts those four parameters.                     |
| FR-SV2    | `start() -> None` — bind the socket, set `SO_REUSEADDR`, begin listening.                                          |
| FR-SV3    | For each accepted connection up to `player_count`, spawn a daemon thread that calls `on_connect(channel)`.          |
| FR-SV4    | After `player_count` connections are accepted, stop accepting new ones (do not call `on_connect` for extras).       |
| FR-SV5    | `stop() -> None` — close the listening socket cleanly; already-running handler threads are not forcibly killed.     |
| FR-SV6    | All host, port, and count values come from parameters — no literals in source.                                       |

---

### 5.4 `TcpClient` — connection initiator (`shared/transport/tcp_client.py`)

**Purpose:** connect to the referee's server socket with configurable retry/backoff.

| ID        | Requirement                                                                                                          |
|-----------|----------------------------------------------------------------------------------------------------------------------|
| FR-CL1    | `TcpClient(host, port, connect_timeout, max_retries, backoff_base)` — constructor.                                  |
| FR-CL2    | `connect() -> Channel` — attempt to connect; on `ConnectionRefusedError`, wait `backoff_base * 2^attempt` seconds and retry up to `max_retries` times. |
| FR-CL3    | If all retries are exhausted, raise `ConnectionFailedError`.                                                         |
| FR-CL4    | Set a socket-level connect timeout using `connect_timeout` (from config).                                            |
| FR-CL5    | `close() -> None` — close the socket cleanly.                                                                        |
| FR-CL6    | Define `ConnectionFailedError(IOError)` in this module.                                                              |
| FR-CL7    | All timeout and retry values come from parameters — no literals in source.                                           |

---

### 5.5 `MessageType` — message type enum (`services/protocol/message_types.py`)

**Purpose:** single authoritative definition of every message type in the lifecycle.
No string literal for a message type appears anywhere else in the codebase.

| ID        | Requirement                                                                                                          |
|-----------|----------------------------------------------------------------------------------------------------------------------|
| FR-MT1    | Define `MessageType(str, Enum)` with members: `REGISTER`, `REGISTER_ACK`, `ROLE_ASSIGN`, `GAME_START`, `MOVE_REQUEST`, `MOVE_SUBMIT`, `STATE_UPDATE`, `GAME_OVER`, `ERROR`, `HEARTBEAT`. |
| FR-MT2    | Each member's value is the lowercase snake_case string of its name (e.g. `REGISTER = "register"`). Used for JSON serialization. |
| FR-MT3    | `MessageType` is importable from `agent_arena.services.protocol`.                                                   |

---

### 5.6 `Envelope` — message wrapper (`services/protocol/envelope.py`)

**Purpose:** typed container for every field that wraps every message, regardless of type.

| ID        | Requirement                                                                                                          |
|-----------|----------------------------------------------------------------------------------------------------------------------|
| FR-EN1    | Define `Envelope` as a `dataclass(frozen=True)` with fields: `protocol_version: str`, `type: MessageType`, `match_id: str \| None`, `sender: str`, `seq: int`, `timestamp: str`, `payload: dict`. |
| FR-EN2    | `match_id` must be explicitly `None` on `REGISTER` messages (no match exists yet — ADR-008).                       |
| FR-EN3    | `timestamp` is an ISO-8601 UTC string. `Envelope` does not generate it — the caller does.                           |
| FR-EN4    | `Envelope` has no knowledge of specific payload contents — `payload` is an opaque `dict`.                           |

---

### 5.7 `Payloads` — per-type payload schemas (`services/protocol/payloads.py`)

**Purpose:** typed dataclasses for each message's payload. Gives callers strong types;
separates from `envelope.py` to respect the ≤ 150-line rule.

| ID        | Requirement                                                                                                          |
|-----------|----------------------------------------------------------------------------------------------------------------------|
| FR-PL1    | Define one `dataclass(frozen=True)` per `MessageType` variant. Naming: `RegisterPayload`, `RegisterAckPayload`, `RoleAssignPayload`, `GameStartPayload`, `MoveRequestPayload`, `MoveSubmitPayload`, `StateUpdatePayload`, `GameOverPayload`, `ErrorPayload`, `HeartbeatPayload`. |
| FR-PL2    | `RegisterPayload`: `agent_id: str`, `agent_name: str`, `protocol_version: str`.                                    |
| FR-PL3    | `RegisterAckPayload`: `accepted: bool`, `match_id: str \| None`, `reason: str \| None`.                           |
| FR-PL4    | `RoleAssignPayload`: `role: str`, `game_config: dict`.                                                              |
| FR-PL5    | `GameStartPayload`: `initial_state: dict`, `turn_order: list[str]`.                                                |
| FR-PL6    | `MoveRequestPayload`: `state: dict`, `legal_moves: list`, `move_timeout_seconds: float`.                           |
| FR-PL7    | `MoveSubmitPayload`: `move: dict`.                                                                                  |
| FR-PL8    | `StateUpdatePayload`: `state: dict`, `last_move: dict`, `active_player: str`.                                      |
| FR-PL9    | `GameOverPayload`: `result: str`, `reason: str`, `final_state: dict`.                                              |
| FR-PL10   | `ErrorPayload`: `code: str`, `message: str`.                                                                        |
| FR-PL11   | `HeartbeatPayload`: `(empty — no fields required)`.                                                                 |

---

### 5.8 `Codec` — serialization (`services/protocol/codec.py`)

**Purpose:** convert between `Envelope` objects and raw bytes that can be sent over the wire.

| ID        | Requirement                                                                                                          |
|-----------|----------------------------------------------------------------------------------------------------------------------|
| FR-CO1    | `encode(envelope: Envelope) -> bytes` — serialize to UTF-8 JSON bytes. `MessageType` values use their string value. |
| FR-CO2    | `decode(data: bytes) -> Envelope` — deserialize UTF-8 JSON bytes back to an `Envelope`.                            |
| FR-CO3    | Round-trip invariant: `decode(encode(envelope)) == envelope` for any valid envelope.                                |
| FR-CO4    | On malformed JSON input to `decode`, raise `CodecError`.                                                            |
| FR-CO5    | On missing required envelope fields in `decode`, raise `CodecError`.                                                |
| FR-CO6    | Define `CodecError(ValueError)` in this module.                                                                     |
| FR-CO7    | `Codec` has no knowledge of which payload fields are valid — that is `Validation`'s job.                           |

---

### 5.9 `Validation` — message contracts (`services/protocol/validation.py`)

**Purpose:** enforce the message contract after decoding. Called immediately after
`Codec.decode()` before any message is handed to a domain service.

| ID        | Requirement                                                                                                          |
|-----------|----------------------------------------------------------------------------------------------------------------------|
| FR-VA1    | `validate(envelope: Envelope, expected_version: str) -> None` — raise on any violation.                            |
| FR-VA2    | If `envelope.protocol_version != expected_version`, raise `ProtocolVersionError`.                                   |
| FR-VA3    | If `envelope.type` is not a valid `MessageType` member, raise `UnknownMessageTypeError`.                            |
| FR-VA4    | If `envelope.match_id` is `None` and `envelope.type != MessageType.REGISTER`, raise `ValidationError`.              |
| FR-VA5    | If `envelope.seq` is not a non-negative integer, raise `ValidationError`.                                           |
| FR-VA6    | Define `ProtocolVersionError(ValueError)`, `UnknownMessageTypeError(ValueError)`, `ValidationError(ValueError)` in this module. |
| FR-VA7    | `validate` does not inspect payload contents — payload schema validation is out of scope for Phase 1.               |

---

## 6. Non-Functional Requirements

| ID      | Requirement                                                                                       |
|---------|---------------------------------------------------------------------------------------------------|
| NL-NFR1 | Transport is fully mockable: `InMemoryChannel` allows unit tests with no real sockets            |
| NL-NFR2 | No domain service (`referee/`, `player/`) imports `socket` directly — only transport modules do  |
| NL-NFR3 | All timeouts and limits come from config parameters; no literal in source                         |
| NL-NFR4 | Codec is stateless: `encode` and `decode` are pure functions with no side effects                 |
| NL-NFR5 | Framing reads are blocking but bounded: `recv_frame` never reads more bytes than declared         |
| NL-NFR6 | Every error type is a subclass of a standard Python exception (`IOError` or `ValueError`)        |

---

## 7. Failure Catalog

| # | Failure                             | Detected by        | Response                                                    |
|---|-------------------------------------|--------------------|-------------------------------------------------------------|
| 1 | TCP packet split (partial frame)    | `Framing.recv_frame` | Buffer and keep reading until complete; transparent to caller |
| 2 | Frame header > `max_frame_size`     | `Framing.recv_frame` | Raise `FrameTooLargeError`; connection must be closed by caller |
| 3 | Peer closes connection mid-read     | `Framing.recv_frame` | Raise `ConnectionClosedError`                               |
| 4 | JSON malformed                      | `Codec.decode`      | Raise `CodecError`                                          |
| 5 | Required envelope field missing     | `Codec.decode`      | Raise `CodecError`                                          |
| 6 | Wrong `protocol_version`            | `Validation.validate` | Raise `ProtocolVersionError`                              |
| 7 | Unknown `type` string               | `Validation.validate` | Raise `UnknownMessageTypeError`                           |
| 8 | `match_id` is `None` on non-REGISTER| `Validation.validate` | Raise `ValidationError`                                  |
| 9 | Referee not yet listening           | `TcpClient.connect` | Retry with backoff; raise `ConnectionFailedError` on exhaustion |
| 10| Third player attempts to connect    | `TcpServer`         | Accept socket then immediately close it (no `on_connect` call) |

---

## 8. Out of Scope

- TLS / encryption (localhost only in Phase 1 and 2)
- Payload-level schema validation (deferred to domain services)
- Message ordering guarantees beyond TCP's own ordering
- Compression of the JSON payload
- Persistent message logs (that is the logging layer's job)
