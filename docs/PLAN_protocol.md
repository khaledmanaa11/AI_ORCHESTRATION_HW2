# Architecture Plan — Protocol Layer (Wire Protocol)

| Field    | Value                                      |
|----------|--------------------------------------------|
| Document | `PLAN_protocol.md`                         |
| Project  | `agent-arena`                              |
| Version  | 1.00                                       |
| Date     | 2026-05-30                                 |
| Status   | Approved                                   |

> Companion: [PRD_protocol.md](PRD_protocol.md) · [TODO_protocol.md](TODO_protocol.md)
> No source code in this document — structure, interfaces in prose, and diagrams only.

---

## 1. Overview

The Protocol Layer defines the structured serialization, framing, and validation rules for messages exchanged between the Referee and Player programs over raw TCP sockets. It decouples the core domain models (game state, LLM decisions, referee scoring) from connection management and network logistics.

```
┌───────────────────────────────────────────────────────────┐
│              RefereeServer / PlayerAgent                  │
│  (Interact with Envelope & Payload structures in Python)  │
└─────────────────────────────┬─────────────────────────────┘
                              │
               encode / decode / validate
                              │
┌─────────────────────────────▼─────────────────────────────┐
│                    PROTOCOL LAYER                         │
│   (Codec, MessageType, ErrorCode, Validation, Payloads)   │
└─────────────────────────────┬─────────────────────────────┘
                              │
                     send / recv (bytes)
                              │
┌─────────────────────────────▼─────────────────────────────┐
│                    TRANSPORT LAYER                        │
│         (FramedChannel, TcpServer, TcpClient)             │
└─────────────────────────────┬─────────────────────────────┘
                              │
                          Raw Sockets
```

The protocol relies on a length-prefix framing transport to solve the partial-read issue over TCP streams, ensuring that the codec receives complete, well-formed message payloads.

---

## 2. File Structure

The protocol modules reside in `services/protocol/`, while the supporting framing and transport helpers live in `shared/transport/`.

```
src/agent_arena/
├── shared/
│   └── transport/
│       ├── channel.py        ← Defines Channel ABC, InMemoryChannel, FramedChannel
│       └── framing.py        ← Low-level send_frame, recv_frame functions
└── services/
    ├── protocol/
    │   ├── __init__.py       ← Re-exports MessageType, ErrorCode, Envelope, Codec, etc.
    │   ├── message_types.py  ← Defines MessageType and ErrorCode Enums
    │   ├── envelope.py       ← Defines the Envelope frozen dataclass
    │   ├── payloads.py       ← Defines individual payload dataclasses (e.g. RegisterPayload)
    │   ├── codec.py          ← Implements serialize/deserialize to JSON
    │   └── validation.py     ← Handles version checks, sequence, and structural validity
    └── referee/
        └── server.py         ← Entry point where validate() is run on REGISTER
```

---

## 3. Building Blocks

### 3.1 `Envelope` & `Payloads`
- **Envelope**: A frozen dataclass serving as the outer message wrapper. All messages must populate fields: `protocol_version`, `type`, `match_id` (None for `REGISTER`), `sender`, `seq`, `timestamp`, and `payload` (opaque dict).
- **Payloads**: Strongly typed, frozen dataclasses mapped to each `MessageType` to guarantee structural consistency when building/consuming message content within domain services.

### 3.2 `MessageType` & `ErrorCode` Enums
- **MessageType**: Authoritative set of strings representing game lifecycle events (`REGISTER`, `GAME_START`, `MOVE_REQUEST`, etc.).
- **ErrorCode**: Authoritative set of strings representing typed error payloads (`VERSION_MISMATCH`, `MALFORMED_MESSAGE`, `UNEXPECTED_MESSAGE`, `MATCH_FULL`).

### 3.3 `Codec`
- **Stateless Serialization**: Serializes/deserializes envelopes to/from UTF-8 JSON.
- **Error Handling**: Raises `CodecError` if JSON is malformed, required envelope keys are missing, or type values are unknown.

### 3.4 `Validation`
- **Guard Enforcement**: Validates version compatibility (`protocol_version == "1.00"`), verifies `match_id` presence (for non-REGISTER messages), and checks sequence indices (`seq >= 0`).

---

## 4. Message Send / Receive Path

### 4.1 Handshake Sequence
```
   Player                                        Referee
     │                                              │
     │  REGISTER (match_id=None)                    │
     ├─────────────────────────────────────────────>┤ [Validate version/type]
     │                                              │ (If wrong, sends ERROR + closes)
     │                                              │
     │  REGISTER_ACK (match_id assigned)            │
     |<─────────────────────────────────────────────┤
     │                                              │
     │  ROLE_ASSIGN (role & game_config)            │
     |<─────────────────────────────────────────────┤
     │                                              │
```

---

## 5. Testing Strategy

- **Unit Tests**:
  - `test_message_types.py`: Confirms enum values and mapping.
  - `test_envelope.py`: Validates immutability and fields.
  - `test_codec.py`: Verifies round-trip encoding/decoding and codec exception triggers.
  - `test_validation.py`: Tests version validation, negative seq handling, and match_id rules.
- **Integration/Lifecycle Tests**:
  - `test_debate_loop.py`: Validates the complete lifecycle over real TCP from registration to GAME_OVER.

---

## 6. Architecture Decision Records (ADR)

| ADR | Decision | Rationale | Trade-off |
|-----|----------|-----------|-----------|
| PL-001 | Strict Version Check | Mismatched clients are rejected early to avoid silent incompatibilities. | Client must use exactly "1.00". |
| PL-002 | Typed Error Codes | Emitting structured string enums (e.g. `VERSION_MISMATCH`) permits automated client handling. | Marginally larger message envelopes. |
| PL-003 | Transport Decorator | `FramedChannel` decouples framing logic from basic TCP read/write channels. | Extra wrapping layer around channels. |
