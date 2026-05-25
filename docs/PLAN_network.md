# Architecture Plan — Network Layer (Transport + Protocol)

| Field    | Value                                      |
|----------|--------------------------------------------|
| Document | `PLAN_network.md`                          |
| Project  | `agent-arena`                              |
| Version  | 1.00                                       |
| Date     | 2026-05-25                                 |
| Status   | Draft                                      |

> Companion: [PRD_network.md](PRD_network.md) · [TODO_network.md](TODO_network.md)
> No source code in this document — structure, interfaces in prose, and diagrams only.

---

## 1. Overview

This phase delivers the two sub-layers that let the three processes exchange structured
messages. Neither sub-layer knows about game rules, roles, or brains.

```
┌────────────────────────────────────────────────────────────────┐
│  Domain services (referee, player) — speak in Envelope objects │
└────────────────────┬───────────────────────────────────────────┘
                     │ encode / decode / validate
┌────────────────────▼───────────────────────────────────────────┐
│  PROTOCOL LAYER                                                │
│  MessageType · Envelope · Payloads · Codec · Validation        │
└────────────────────┬───────────────────────────────────────────┘
                     │ send_frame / recv_frame
┌────────────────────▼───────────────────────────────────────────┐
│  TRANSPORT LAYER                                               │
│  Channel (abstract) · Framing · TcpServer · TcpClient         │
└────────────────────┬───────────────────────────────────────────┘
                     │ raw bytes
                  TCP socket
```

**Key rule:** flow is strictly top-down. Protocol imports Transport; Transport imports
nothing from Protocol or Domain. Domain never imports `socket`.

---

## 2. File Structure

Only new files and one update per package `__init__`.

```
src/agent_arena/
├── shared/
│   └── transport/
│       ├── __init__.py       ← re-export Channel, InMemoryChannel, ConnectionClosedError
│       ├── channel.py        ← Channel ABC + InMemoryChannel + ConnectionClosedError  (NEW)
│       ├── framing.py        ← send_frame, recv_frame, FrameTooLargeError             (NEW)
│       ├── tcp_server.py     ← TcpServer                                              (NEW)
│       └── tcp_client.py     ← TcpClient, ConnectionFailedError                      (NEW)
└── services/
    └── protocol/
        ├── __init__.py       ← re-export all public names
        ├── message_types.py  ← MessageType enum                                       (NEW)
        ├── envelope.py       ← Envelope dataclass                                     (NEW)
        ├── payloads.py       ← one dataclass per MessageType                          (NEW)
        ├── codec.py          ← encode / decode, CodecError                            (NEW)
        └── validation.py     ← validate, ProtocolVersionError, UnknownMessageTypeError,
                                 ValidationError                                        (NEW)

tests/unit/
├── shared/
│   └── transport/
│       ├── __init__.py
│       ├── test_channel.py      (NEW)
│       ├── test_framing.py      (NEW)
│       ├── test_tcp_server.py   (NEW)
│       └── test_tcp_client.py   (NEW)
└── services/
    └── protocol/
        ├── __init__.py
        ├── test_message_types.py  (NEW)
        ├── test_envelope.py       (NEW)
        ├── test_payloads.py       (NEW)
        ├── test_codec.py          (NEW)
        └── test_validation.py     (NEW)
```

---

## 3. Building Blocks

### 3.1 `Channel` + `InMemoryChannel`

- **Purpose:** abstract transport interface; `InMemoryChannel` is the test double.
- **Setup:** `InMemoryChannel.make_pair()` returns `(channel_a, channel_b)` backed by
  two `queue.Queue` instances — each side's `send` pushes to the other side's receive queue.
- **Input:** `send(data: bytes)` — raw bytes, already framed.
- **Output:** `recv() -> bytes` — raw bytes, already framed.
- **Key invariant:** `recv()` blocks until data is available or the peer closes.
  When the peer closes, it raises `ConnectionClosedError`.

### 3.2 `Framing`

- **Purpose:** eliminate the partial-read problem. TCP is a byte stream; `Framing`
  imposes message boundaries.
- **Setup:** stateless — two module-level functions; no class.
- **Input:** a `Channel` + raw message bytes (for `send_frame`), or a `Channel` +
  `max_bytes` limit (for `recv_frame`).
- **Output:** nothing on send; the complete message bytes on receive.
- **Key invariant:** `recv_frame` loops internally until it has accumulated exactly the
  number of bytes declared in the header. Callers never see partial messages.
- **Why 4-byte big-endian:** supports up to ~4 GB frames; big-endian is the network
  byte order convention; simple to implement with `struct.pack(">I", n)`.

### 3.3 `TcpServer`

- **Purpose:** manage the TCP listen socket and dispatch one thread per accepted connection.
- **Setup:** instantiated with `host`, `port`, `player_count`, and `on_connect` callback.
- **Input:** OS connection events (via `socket.accept()`).
- **Output:** calls `on_connect(TcpChannel)` in a new daemon thread for each accepted
  connection (up to `player_count`).
- **Key invariant:** after `player_count` connections are accepted, the server stops
  calling `accept()` — no more `on_connect` calls. Extra TCP connections are accepted at
  the socket level then immediately closed (to avoid keeping them in the OS backlog).
- **TcpChannel:** a thin `Channel` subclass that wraps a single accepted `socket`.
  Its `send` calls `socket.sendall`; its `recv` calls `socket.recv`.

### 3.4 `TcpClient`

- **Purpose:** establish the player's outbound connection to the referee, with retry.
- **Setup:** instantiated with connection parameters from config.
- **Input:** `connect()` call.
- **Output:** returns a `TcpChannel` on success; raises `ConnectionFailedError` if all
  retries are exhausted.
- **Backoff formula:** `wait = backoff_base * (2 ** attempt)` — doubles each retry.
  Example with `backoff_base=0.5`: waits 0.5 s, 1 s, 2 s, 4 s …

### 3.5 `MessageType`

- **Purpose:** the single source of truth for all message type strings.
- **Key invariant:** no string literal for a message type appears outside this file.
  Comparisons always go through the enum.

### 3.6 `Envelope`

- **Purpose:** the outer wrapper around every message. Carries routing and sequencing
  metadata; the `payload` dict carries the message-specific content.
- **Frozen dataclass:** immutable after construction — safe to pass between threads.
- **`match_id` is `None` exactly once:** on `REGISTER`. The referee assigns the
  `match_id` in `REGISTER_ACK` and it is present on every subsequent message.

### 3.7 `Payloads`

- **Purpose:** give domain services strongly-typed access to payload content without
  parsing raw dicts at every call site.
- **Not enforced by `Codec`:** `Codec` only works with the envelope and treats `payload`
  as an opaque dict. Domain services convert to/from payload dataclasses when needed.
- **Frozen dataclasses:** same thread-safety guarantee as `Envelope`.

### 3.8 `Codec`

- **Purpose:** the only place where Python objects become bytes and bytes become Python
  objects.
- **Stateless:** `encode` and `decode` are pure functions; no class needed.
- **`MessageType` serialization:** stored as its string value (e.g. `"register"`);
  deserialized back via `MessageType(value)`.

### 3.9 `Validation`

- **Purpose:** enforce the message contract after decoding and before dispatch.
- **Called immediately** after every `Codec.decode()` — think of it as a gate between
  the wire and domain logic.
- **Does not validate payloads:** payload schemas are the domain service's responsibility.
  This keeps `Validation` minimal and testable.

---

## 4. Message Send / Receive Path

### 4.1 Sending a message (referee → player example)

```
Referee domain service
  creates Envelope(type=GAME_START, payload={...})
    → Codec.encode(envelope) → bytes
      → Framing.send_frame(channel, bytes)
        → channel.send(4-byte-header + payload-bytes)
          → TCP socket
```

### 4.2 Receiving a message (player reading from referee)

```
TCP socket
  → channel.recv() → raw bytes arrive
    → Framing.recv_frame(channel, max_bytes) → complete message bytes
      → Codec.decode(bytes) → Envelope
        → Validation.validate(envelope, PROTOCOL_VERSION)
          → domain service handles the envelope
```

---

## 5. Thread Model Inside `TcpServer`

```
Main thread (referee startup)
  └─ TcpServer.start()
       └─ accept loop thread (daemon)
            ├─ accept() → player A socket → spawn handler thread A (daemon)
            ├─ accept() → player B socket → spawn handler thread B (daemon)
            └─ (player_count reached — stop accepting)

Handler thread A: calls on_connect(channel_A) → referee matchmaking logic
Handler thread B: calls on_connect(channel_B) → referee matchmaking logic
```

The fault-tolerance components (`WatchdogThread`, `HeartbeatSender`) are started by the
referee **after** both handler threads are running — that wiring belongs in Phase 4.

---

## 6. Testing Strategy

| Module          | Test approach                                                              |
|-----------------|---------------------------------------------------------------------------|
| `Channel`       | InMemoryChannel: concurrent send/recv in two threads                      |
| `Framing`       | InMemoryChannel as transport; test split reads by chunking bytes manually |
| `TcpServer`     | Real localhost sockets; short test port from OS (`port=0`)                |
| `TcpClient`     | Real localhost sockets; test retry by delaying server start               |
| `MessageType`   | Enum members, string values, unknown-value handling                       |
| `Envelope`      | Construction, `match_id=None` on REGISTER, frozen immutability            |
| `Payloads`      | Each payload dataclass; frozen; round-trip through `asdict`               |
| `Codec`         | Encode→decode round-trip; malformed JSON; missing fields                  |
| `Validation`    | Version mismatch; unknown type; null match_id on non-REGISTER; bad seq    |

All unit tests use `InMemoryChannel` — no real sockets except in `test_tcp_server.py`
and `test_tcp_client.py`.

---

## 7. Architecture Decision Records

| ADR     | Decision                                                    | Rationale                                                         | Trade-off                                      |
|---------|-------------------------------------------------------------|-------------------------------------------------------------------|------------------------------------------------|
| NL-001  | `Channel` is an ABC, not a protocol/duck type               | `isinstance` checks in tests; clear contract for implementors     | Slightly more ceremony than duck typing        |
| NL-002  | `InMemoryChannel` uses `queue.Queue`, not `io.BytesIO`      | Thread-safe by design; blocks on `recv` naturally                 | Can't seek; that's intentional                 |
| NL-003  | `Framing` is two module-level functions, not a class        | Framing is stateless; no need to instantiate it                   | Must pass `channel` every call                 |
| NL-004  | `Codec` is stateless (functions, not class)                 | No shared state; trivially thread-safe                            | Can't swap codec without changing call sites   |
| NL-005  | `Validation.validate` raises, never returns a result object | Simpler callers — guard at the gate, not a result type to check   | Less composable; acceptable at this scale      |
| NL-006  | `Payloads` are separate from `Envelope`                     | Stays within ≤ 150 line rule; single responsibility               | Two imports instead of one at call sites       |
| NL-007  | `TcpServer` accepts then closes extra connections           | Avoids holding them in OS backlog indefinitely                    | Third client sees a closed connection, not a hang |
| NL-008  | `TcpClient` uses exponential backoff                        | Prevents thundering-herd if referee starts late                   | Max wait grows quickly; cap with `max_retries` |

---

## 8. Integration with Fault Tolerance (Phase 4/5)

The fault tolerance tools (`ShutdownCoordinator`, `WatchdogThread`, `HeartbeatSender`)
built in the previous phase are wired into the referee and player at startup — that wiring
is deferred to Phase 4 (Referee) and Phase 5 (Player), not this phase.

The integration points to keep in mind while building this layer:

- Every `recv_frame` call can raise `ConnectionClosedError` — that exception is the signal
  that triggers `coordinator.request_shutdown("player_disconnect:...")` in Phase 4.
- `HeartbeatSender.send_fn` will call `Codec.encode` + `Framing.send_frame` on a
  `HEARTBEAT` envelope — this layer must support that call cleanly.
- `WatchdogThread.heartbeat(peer)` is called every time `recv_frame` returns successfully
  — the framing layer has no knowledge of this; the caller handles it.
