# Task Tracking — Protocol Layer (Wire Protocol)

| Field    | Value                                      |
|----------|--------------------------------------------|
| Document | `TODO_protocol.md`                         |
| Project  | `agent-arena`                              |
| Version  | 1.00                                       |
| Date     | 2026-05-30                                 |

> Status: `[ ]` not started · `[~]` in progress · `[x]` done
> Every task maps to at least one requirement in [PRD_protocol.md](PRD_protocol.md).
> Companion: [PLAN_protocol.md](PLAN_protocol.md)

---

## Module A — Message Types & Error Codes (`services/protocol/message_types.py`)

### A1 — Define Authoritative MessageType Enum
- [x] **A1.1** Define `MessageType` string enum with all 10 message lifecycle events.
  - *DoD/Evidence:* `src/agent_arena/services/protocol/message_types.py:4-16`

### A2 — Define Authoritative ErrorCode Enum
- [x] **A2.1** Define `ErrorCode` string enum with standardized error codes.
  - *DoD/Evidence:* `src/agent_arena/services/protocol/message_types.py:19-31`

---

## Module B — Envelopes & Payloads (`services/protocol/envelope.py`, `payloads.py`)

### B1 — Define Envelope Dataclass
- [x] **B1.1** Define `@dataclass(frozen=True) class Envelope` wrapping standard envelope fields.
  - *DoD/Evidence:* `src/agent_arena/services/protocol/envelope.py:6-16`

### B2 — Define Payload Dataclasses
- [x] **B2.1** Implement strongly typed payload structures for all message types.
  - *DoD/Evidence:* `src/agent_arena/services/protocol/payloads.py:5-65`

---

## Module C — Codec & Serialization (`services/protocol/codec.py`)

### C1 — Implement Codec Serialization/Deserialization
- [x] **C1.1** Implement `encode(envelope)` and `decode(data)` for UTF-8 encoded JSON.
  - *DoD/Evidence:* `src/agent_arena/services/protocol/codec.py:17-55`

---

## Module D — Validation (`services/protocol/validation.py`)

### D1 — Implement Validation Logic
- [x] **D1.1** Implement `validate(envelope, expected_version)` to enforce version, matching, and sequence constraints.
  - *DoD/Evidence:* `src/agent_arena/services/protocol/validation.py:5-30`

---

## Module E — Framing & Channel Decorators (`shared/transport/framing.py`, `channel.py`)

### E1 — Implement Low-Level Framing
- [x] **E1.1** Implement length-prefix big-endian framing reader and writer.
  - *DoD/Evidence:* `src/agent_arena/shared/transport/framing.py:9-36`

### E2 — Implement FramedChannel Decorator
- [x] **E2.1** Wrap raw transport channels in a `FramedChannel` that enforces the maximum frame size.
  - *DoD/Evidence:* `src/agent_arena/shared/transport/channel.py:47-89`

---

## Module F — Timeout Enforcement (`shared/transport/tcp_client.py`, `services/referee/server.py`)

### F1 — Implement Connection and Post-Handshake Timeout Enforcement
- [x] **F1.1** Ensure connect timeouts are read from config and applied during TCP client connect attempts.
  - *DoD/Evidence:* `src/agent_arena/shared/transport/tcp_client.py:23,37`
- [x] **F1.2** Wire `WatchdogThread` to monitor post-handshake connection states and trigger shutdown on read timeout.
  - *DoD/Evidence:* `src/agent_arena/services/referee/server.py:65-68,165` and `src/agent_arena/services/player/agent.py:89-90`

---

## Module G — Matchmaking Handshake Flow (`services/referee/server.py`)

### G1 — Implement Matchmaker Registration
- [x] **G1.1** Handle handshake registration flow (`REGISTER` -> `REGISTER_ACK` -> `ROLE_ASSIGN`).
  - *DoD/Evidence:* `src/agent_arena/services/referee/server.py:131-207`

---

## Module H — Version Validation & Rejection (`services/referee/server.py`)

### H1 — Enforce Validation on Connection
- [x] **H1.1** Validate incoming REGISTER envelopes immediately using `validate()` and send typed ERROR codes for mismatches.
  - *DoD/Evidence:* `src/agent_arena/services/referee/server.py:139-148`

---

## Requirement traceability matrix

| PRD Requirement | Covered by tasks |
|---|---|
| Section 2.1 (Framing Format) | Module E (Framing & Channel Decorators) |
| Section 2.2 (Envelope Schema) | Module B (Envelope & Payloads) |
| Section 3 (Maximum Frame Size) | Module E (Framing & Channel Decorators) |
| Section 3 (Encoding: UTF-8) | Module C (Codec & Serialization) |
| Section 3 (Timeout: Connect/Read/Write) | Module F (Timeout Enforcement) |
| Section 5 (Success - Happy Path registration) | Module G (Matchmaking Handshake Flow) |
| Section 5 (Edge Case - Protocol version mismatch) | Module H (Version Validation & Rejection) |
| Section 5 (Edge Case - Truncated Frame / Partial Read) | Module E (Framing & Channel Decorators) |
| Section 5 (Edge Case - Oversized Frame) | Module E (Framing & Channel Decorators) |
