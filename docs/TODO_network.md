# Task Tracking — Network Layer (Transport + Protocol)

| Field    | Value                                      |
|----------|--------------------------------------------|
| Document | `TODO_network.md`                          |
| Project  | `agent-arena`                              |
| Version  | 1.00                                       |
| Date     | 2026-05-25                                 |

> Status: `[ ]` not started · `[~]` in progress · `[x]` done
> Every task maps to at least one requirement in [PRD_network.md](PRD_network.md).
> Companion: [PLAN_network.md](PLAN_network.md)

---

## Module A — `Channel` + `InMemoryChannel` (`shared/transport/channel.py`)

> PRD coverage: FR-CH1 through FR-CH5

### A1 — File setup
- [x] **A1.1** Create `src/agent_arena/shared/transport/channel.py`.
  - *DoD:* file exists; `ruff check` passes on an empty file.
- [x] **A1.2** Add imports: `import queue`, `from abc import ABC, abstractmethod`.
  - *DoD:* no unused imports; ruff clean.
- [x] **A1.3** Define `ConnectionClosedError(IOError)` with a one-line docstring (FR-CH5).
  - *DoD:* `raise ConnectionClosedError("test")` works.

### A2 — `Channel` ABC
- [x] **A2.1** Define `class Channel(ABC)` with docstring: *"Abstract transport interface. Domain services never touch sockets directly."*
  - *DoD:* class exists and is importable.
- [x] **A2.2** Declare `@abstractmethod send(self, data: bytes) -> None`.
  - *DoD:* calling `send` on a bare `Channel` raises `TypeError`.
- [x] **A2.3** Declare `@abstractmethod recv(self) -> bytes`.
  - *DoD:* same.

### A3 — `InMemoryChannel`
- [x] **A3.1** Define `class InMemoryChannel(Channel)`.
  - *DoD:* class is importable; passes `isinstance(ch, Channel)`.
- [x] **A3.2** `__init__(self, in_q: queue.Queue, out_q: queue.Queue) -> None`. Store both queues.
  - *DoD:* attributes exist.
- [x] **A3.3** Implement `send(self, data: bytes) -> None`: put `data` on `out_q`.
  - *DoD:* `ch_a.send(b"hello")` → `ch_b.recv()` returns `b"hello"`.
- [x] **A3.4** Implement `recv(self) -> bytes`: get from `in_q` (blocking). If sentinel `None` is received, raise `ConnectionClosedError`.
  - *DoD:* blocks until data arrives; raises `ConnectionClosedError` on `None`.
- [x] **A3.5** Implement `close(self) -> None`: put `None` sentinel on `out_q` to signal peer.
  - *DoD:* `ch_a.close()` → `ch_b.recv()` raises `ConnectionClosedError`.
- [x] **A3.6** Implement `@classmethod make_pair(cls) -> tuple["InMemoryChannel", "InMemoryChannel"]`: create two shared queues and return two linked channels.
  - *DoD:* `a, b = InMemoryChannel.make_pair(); a.send(b"x"); assert b.recv() == b"x"`.

### A4 — Unit tests for `Channel`
- [x] **A4.1** Create `tests/unit/shared/transport/__init__.py` and `tests/unit/shared/transport/test_channel.py`.
  - *DoD:* pytest collects the file with 0 errors.
- [x] **A4.2** Test `make_pair()` — send from A, receive on B.
  - *DoD:* `b.recv() == b"hello"`.
- [x] **A4.3** Test bidirectional: send on B, receive on A.
  - *DoD:* both directions work independently.
- [x] **A4.4** Test `close()` — receiving after peer closes raises `ConnectionClosedError`.
  - *DoD:* `ch_a.close(); ch_b.recv()` raises `ConnectionClosedError`.
- [x] **A4.5** Test thread safety: 10 threads each send 100 messages; receiver collects all.
  - *DoD:* received count == 1000; no exception.
- [x] **A4.6** Test `Channel` is abstract — instantiating it directly raises `TypeError`.
  - *DoD:* `Channel()` raises `TypeError`.

---

## Module B — `Framing` (`shared/transport/framing.py`)

> PRD coverage: FR-FR1 through FR-FR7

### B1 — File setup
- [x] **B1.1** Create `src/agent_arena/shared/transport/framing.py`.
  - *DoD:* file exists; ruff clean.
- [x] **B1.2** Add imports: `import struct`, `from agent_arena.shared.transport.channel import Channel, ConnectionClosedError`.
  - *DoD:* imports resolve.
- [x] **B1.3** Define `FrameTooLargeError(IOError)` with a one-line docstring (FR-FR6).
  - *DoD:* raisable.
- [x] **B1.4** Define module-level constant `_HEADER_FORMAT = ">I"` and `_HEADER_SIZE = 4`.
  - *DoD:* `struct.calcsize(_HEADER_FORMAT) == 4`.

### B2 — `send_frame`
- [x] **B2.1** Implement `send_frame(channel: Channel, data: bytes) -> None` (FR-FR1).
  - *DoD:* function exists.
- [x] **B2.2** Inside `send_frame`: pack `len(data)` as 4-byte big-endian; concatenate with `data`; call `channel.send()` once.
  - *DoD:* receiver sees exactly `4 + len(data)` bytes.

### B3 — `recv_frame`
- [x] **B3.1** Implement `recv_frame(channel: Channel, max_bytes: int) -> bytes` (FR-FR2).
  - *DoD:* function exists.
- [x] **B3.2** Read exactly 4 bytes for the header by looping on `channel.recv()` until 4 bytes accumulated (FR-FR4).
  - *DoD:* works even if `recv` returns 1 byte at a time.
- [x] **B3.3** Unpack header to get `payload_length`. If `payload_length > max_bytes`, raise `FrameTooLargeError` immediately without reading more (FR-FR3).
  - *DoD:* `FrameTooLargeError` raised; no payload bytes consumed.
- [x] **B3.4** Read exactly `payload_length` bytes by looping on `channel.recv()` (FR-FR4).
  - *DoD:* works correctly when payload is split across multiple `recv()` calls.
- [x] **B3.5** If `channel.recv()` returns empty bytes `b""` at any point during reading, raise `ConnectionClosedError` (FR-FR5).
  - *DoD:* mid-frame close raises `ConnectionClosedError`.

### B4 — Unit tests for `Framing`
- [x] **B4.1** Create `tests/unit/shared/transport/test_framing.py`.
  - *DoD:* collected by pytest.
- [x] **B4.2** Test happy path: `send_frame` + `recv_frame` round-trips arbitrary bytes.
  - *DoD:* `recv_frame` returns exactly the same bytes passed to `send_frame`.
- [x] **B4.3** Test empty payload (0 bytes) is handled without error.
  - *DoD:* `recv_frame` returns `b""`.
- [x] **B4.4** Test oversized frame raises `FrameTooLargeError` (FR-FR3).
  - *DoD:* `max_bytes=10`, payload=11 bytes → `FrameTooLargeError`.
- [x] **B4.5** Test split payload: simulate `recv()` returning 1 byte at a time (FR-FR4).
  - *DoD:* `recv_frame` still returns the complete message.
- [x] **B4.6** Test peer close during header read raises `ConnectionClosedError`.
  - *DoD:* channel closed before 4 bytes sent → `ConnectionClosedError`.
- [x] **B4.7** Test peer close during payload read raises `ConnectionClosedError`.
  - *DoD:* header sent (declaring 100 bytes), channel closed after 50 bytes → `ConnectionClosedError`.

---

## Module C — `TcpServer` (`shared/transport/tcp_server.py`)

> PRD coverage: FR-SV1 through FR-SV6

### C1 — File setup
- [x] **C1.1** Create `src/agent_arena/shared/transport/tcp_server.py`.
  - *DoD:* file exists; ruff clean.
- [x] **C1.2** Add imports: `import logging`, `import socket`, `import threading`, `from collections.abc import Callable`.
  - *DoD:* no unused imports.
- [x] **C1.3** Create module-level logger: `logger = logging.getLogger(__name__)`.
  - *DoD:* logger name is `"agent_arena.shared.transport.tcp_server"`.

### C2 — `TcpChannel` (inner class / helper)
- [x] **C2.1** Define `class TcpChannel(Channel)` in the same file.
  - *DoD:* `isinstance(tc, Channel)` is `True`.
- [x] **C2.2** `__init__(self, sock: socket.socket)`. Store `self._sock = sock`.
  - *DoD:* attribute exists.
- [x] **C2.3** Implement `send(self, data: bytes) -> None`: call `self._sock.sendall(data)`.
  - *DoD:* bytes arrive intact on the other end.
- [x] **C2.4** Implement `recv(self) -> bytes`: call `self._sock.recv(4096)`. If it returns `b""`, raise `ConnectionClosedError`.
  - *DoD:* empty `recv` → `ConnectionClosedError`.
- [x] **C2.5** Implement `close(self) -> None`: call `self._sock.close()` inside `try/except OSError`.
  - *DoD:* double-close does not raise.

### C3 — `TcpServer`
- [x] **C3.1** Define `class TcpServer`. Constructor: `__init__(self, host: str, port: int, player_count: int, on_connect: Callable[[Channel], None]) -> None`.
  - *DoD:* instantiable with those four params.
- [x] **C3.2** Implement `start(self) -> None`: create socket; set `SO_REUSEADDR`; bind; listen; start the accept loop in a daemon thread (FR-SV2).
  - *DoD:* server is listening after `start()`.
- [x] **C3.3** Accept loop: call `accept()` up to `player_count` times, each time spawning a daemon thread that calls `on_connect(TcpChannel(sock))` (FR-SV3).
  - *DoD:* `on_connect` is called exactly `player_count` times.
- [x] **C3.4** After `player_count` connections are accepted, stop the accept loop. Any extra connection is accepted at socket level then immediately closed (FR-SV4).
  - *DoD:* third client connection is closed by the server.
- [x] **C3.5** Implement `stop(self) -> None`: close the listening socket (FR-SV5).
  - *DoD:* `stop()` does not block; handler threads continue.

### C4 — Unit tests for `TcpServer`
- [x] **C4.1** Create `tests/unit/shared/transport/test_tcp_server.py`.
  - *DoD:* collected by pytest.
- [x] **C4.2** Test: start server on `port=0` (OS picks port); connect 2 clients; `on_connect` called twice.
  - *DoD:* `call_count == 2`.
- [x] **C4.3** Test: third client connection is closed immediately (server rejects it).
  - *DoD:* third client's `recv()` returns `b""` or raises `ConnectionResetError`.
- [x] **C4.4** Test: data sent by a client is received in the `on_connect` handler.
  - *DoD:* `channel.recv()` in handler returns exactly what client sent.
- [x] **C4.5** Test: `stop()` causes the server's accept loop to exit without error.
  - *DoD:* server thread is no longer alive after `stop()`.

---

## Module D — `TcpClient` (`shared/transport/tcp_client.py`)

> PRD coverage: FR-CL1 through FR-CL7

### D1 — File setup
- [x] **D1.1** Create `src/agent_arena/shared/transport/tcp_client.py`.
  - *DoD:* file exists; ruff clean.
- [x] **D1.2** Add imports: `import logging`, `import socket`, `import time`.
  - *DoD:* no unused imports.
- [x] **D1.3** Define `ConnectionFailedError(IOError)` (FR-CL6).
  - *DoD:* raisable.

### D2 — `TcpClient`
- [x] **D2.1** `class TcpClient`. Constructor: `__init__(self, host: str, port: int, connect_timeout: float, max_retries: int, backoff_base: float) -> None`.
  - *DoD:* instantiable.
- [x] **D2.2** Implement `connect(self) -> Channel` (FR-CL2).
  - *DoD:* returns a `TcpChannel` on success.
- [x] **D2.3** On `ConnectionRefusedError`, wait `backoff_base * (2 ** attempt)` seconds and retry. After `max_retries` failures, raise `ConnectionFailedError` (FR-CL2, FR-CL3).
  - *DoD:* `max_retries=2`, server never starts → `ConnectionFailedError` after 2 retries.
- [x] **D2.4** Set socket-level timeout via `socket.settimeout(connect_timeout)` before `connect()` (FR-CL4).
  - *DoD:* connect attempt times out if server doesn't respond within `connect_timeout`.
- [x] **D2.5** Implement `close(self) -> None`: close the socket inside `try/except OSError` (FR-CL5).
  - *DoD:* safe to call even if not connected.

### D3 — Unit tests for `TcpClient`
- [x] **D3.1** Create `tests/unit/shared/transport/test_tcp_client.py`.
  - *DoD:* collected by pytest.
- [x] **D3.2** Test: connect to a running server returns a `Channel`.
  - *DoD:* `isinstance(ch, Channel)` is `True`.
- [x] **D3.3** Test: connect to a non-existent server exhausts retries and raises `ConnectionFailedError`.
  - *DoD:* use `max_retries=1`, `backoff_base=0.01` for fast test.
- [x] **D3.4** Test: data sent through the returned `Channel` is received by the server.
  - *DoD:* end-to-end send/recv over real TCP.

---

## Module E — `MessageType`, `Envelope`, `Payloads` (`services/protocol/`)

> PRD coverage: FR-MT1–FR-MT3, FR-EN1–FR-EN4, FR-PL1–FR-PL11

### E1 — `message_types.py`
- [x] **E1.1** Create `src/agent_arena/services/protocol/message_types.py`.
  - *DoD:* file exists; ruff clean.
- [x] **E1.2** Import `from enum import Enum`.
  - *DoD:* no unused imports.
- [x] **E1.3** Define `class MessageType(str, Enum)` with all 10 members: `REGISTER = "register"`, `REGISTER_ACK = "register_ack"`, `ROLE_ASSIGN = "role_assign"`, `GAME_START = "game_start"`, `MOVE_REQUEST = "move_request"`, `MOVE_SUBMIT = "move_submit"`, `STATE_UPDATE = "state_update"`, `GAME_OVER = "game_over"`, `ERROR = "error"`, `HEARTBEAT = "heartbeat"` (FR-MT1, FR-MT2).
  - *DoD:* `MessageType("register") == MessageType.REGISTER`.
- [x] **E1.4** Create `tests/unit/services/__init__.py`, `tests/unit/services/protocol/__init__.py`, `tests/unit/services/protocol/test_message_types.py`.
  - *DoD:* pytest collects the file.
- [x] **E1.5** Test all 10 members exist and their string values are lowercase with underscores.
  - *DoD:* `MessageType.GAME_START.value == "game_start"`.
- [x] **E1.6** Test that an unknown string raises `ValueError`.
  - *DoD:* `MessageType("banana")` raises `ValueError`.

### E2 — `envelope.py`
- [x] **E2.1** Create `src/agent_arena/services/protocol/envelope.py`.
  - *DoD:* file exists; ruff clean.
- [x] **E2.2** Add imports: `from dataclasses import dataclass`, `from agent_arena.services.protocol.message_types import MessageType`.
  - *DoD:* imports resolve.
- [x] **E2.3** Define `@dataclass(frozen=True) class Envelope` with all 7 fields (FR-EN1).
  - *DoD:* constructable with all fields.
- [x] **E2.4** Confirm `match_id: str | None` field type annotation allows `None` (FR-EN2).
  - *DoD:* `Envelope(..., match_id=None, ...)` does not raise.
- [x] **E2.5** Create `tests/unit/services/protocol/test_envelope.py`.
  - *DoD:* collected by pytest.
- [x] **E2.6** Test construction with `match_id=None` (REGISTER case) and with a string ID.
  - *DoD:* both cases construct without error.
- [x] **E2.7** Test frozen: attempting to set an attribute raises `FrozenInstanceError`.
  - *DoD:* `env.sender = "x"` raises `dataclasses.FrozenInstanceError`.

### E3 — `payloads.py`
- [x] **E3.1** Create `src/agent_arena/services/protocol/payloads.py`.
  - *DoD:* file exists; ruff clean.
- [x] **E3.2** Add `from dataclasses import dataclass, field` and `from typing import Any`.
  - *DoD:* no unused imports.
- [x] **E3.3** Define all 10 payload dataclasses as `@dataclass(frozen=True)` (FR-PL1 through FR-PL11).
  - *DoD:* all 10 classes exist and are importable.
- [x] **E3.4** Verify `HeartbeatPayload` has no required fields (FR-PL11). Constructable with `HeartbeatPayload()`.
  - *DoD:* `HeartbeatPayload()` does not raise.
- [x] **E3.5** Create `tests/unit/services/protocol/test_payloads.py`.
  - *DoD:* collected.
- [x] **E3.6** Test each payload dataclass is constructable with valid data.
  - *DoD:* 10 tests, one per payload type; all pass.
- [x] **E3.7** Test each payload is frozen (pick 3 representative ones).
  - *DoD:* attribute assignment raises `FrozenInstanceError`.

---

## Module F — `Codec` (`services/protocol/codec.py`)

> PRD coverage: FR-CO1 through FR-CO7

### F1 — File setup
- [x] **F1.1** Create `src/agent_arena/services/protocol/codec.py`.
  - *DoD:* file exists; ruff clean.
- [x] **F1.2** Add imports: `import json`, and imports for `Envelope`, `MessageType`.
  - *DoD:* no unused imports.
- [x] **F1.3** Define `CodecError(ValueError)` (FR-CO6).
  - *DoD:* raisable.

### F2 — `encode`
- [x] **F2.1** Implement `encode(envelope: Envelope) -> bytes` (FR-CO1).
  - *DoD:* function exists.
- [x] **F2.2** Convert `envelope` to a dict. Serialize `envelope.type` as its string value (e.g. `"game_start"`).
  - *DoD:* `json.loads(encode(env))["type"] == "game_start"`.
- [x] **F2.3** Serialize the dict to UTF-8 JSON bytes using `json.dumps(...).encode("utf-8")`.
  - *DoD:* result is `bytes`.

### F3 — `decode`
- [x] **F3.1** Implement `decode(data: bytes) -> Envelope` (FR-CO2).
  - *DoD:* function exists.
- [x] **F3.2** Parse JSON: wrap in `try/except json.JSONDecodeError`; raise `CodecError` on failure (FR-CO4).
  - *DoD:* `decode(b"not json")` raises `CodecError`.
- [x] **F3.3** Extract all required fields from the dict. Wrap in `try/except KeyError`; raise `CodecError` on missing field (FR-CO5).
  - *DoD:* `decode(b'{"type": "register"}')` raises `CodecError` (missing other fields).
- [x] **F3.4** Reconstruct `MessageType` from the string value. If unrecognized, raise `CodecError`.
  - *DoD:* `decode` with `"type": "banana"` raises `CodecError`.
- [x] **F3.5** Return a valid `Envelope` object.
  - *DoD:* `isinstance(decode(encode(env)), Envelope)` is `True`.

### F4 — Unit tests for `Codec`
- [x] **F4.1** Create `tests/unit/services/protocol/test_codec.py`.
  - *DoD:* collected by pytest.
- [x] **F4.2** Test encode → decode round-trip for every `MessageType` (10 tests or one parametrized).
  - *DoD:* `decode(encode(env)) == env` for all types.
- [x] **F4.3** Test `decode(b"not json")` raises `CodecError`.
  - *DoD:* assertion passes.
- [x] **F4.4** Test `decode` with missing `sender` field raises `CodecError`.
  - *DoD:* assertion passes.
- [x] **F4.5** Test `decode` with unknown `type` value raises `CodecError`.
  - *DoD:* assertion passes.
- [x] **F4.6** Test that `encode` output is valid UTF-8 and parseable by `json.loads`.
  - *DoD:* `json.loads(encode(env))` does not raise.

---

## Module G — `Validation` (`services/protocol/validation.py`)

> PRD coverage: FR-VA1 through FR-VA7

### G1 — File setup
- [x] **G1.1** Create `src/agent_arena/services/protocol/validation.py`.
  - *DoD:* file exists; ruff clean.
- [x] **G1.2** Add imports: `from agent_arena.services.protocol.envelope import Envelope`, `from agent_arena.services.protocol.message_types import MessageType`.
  - *DoD:* imports resolve.
- [x] **G1.3** Define `ProtocolVersionError(ValueError)`, `UnknownMessageTypeError(ValueError)`, `ValidationError(ValueError)` (FR-VA6).
  - *DoD:* all three raisable.

### G2 — `validate`
- [x] **G2.1** Implement `validate(envelope: Envelope, expected_version: str) -> None` (FR-VA1).
  - *DoD:* function exists.
- [x] **G2.2** If `envelope.protocol_version != expected_version`, raise `ProtocolVersionError` (FR-VA2).
  - *DoD:* version mismatch → `ProtocolVersionError`.
- [x] **G2.3** If `envelope.type` is not a valid `MessageType` member, raise `UnknownMessageTypeError` (FR-VA3). *(This should not happen if `Codec.decode` is called first — but validate defensively.)*
  - *DoD:* an `Envelope` constructed with a raw string type bypassing `Codec` is caught here.
- [x] **G2.4** If `envelope.match_id is None` and `envelope.type != MessageType.REGISTER`, raise `ValidationError` (FR-VA4).
  - *DoD:* `GAME_START` with `match_id=None` → `ValidationError`.
- [x] **G2.5** If `envelope.seq < 0`, raise `ValidationError` (FR-VA5).
  - *DoD:* `seq=-1` → `ValidationError`.
- [x] **G2.6** If all checks pass, return `None` without raising.
  - *DoD:* valid `REGISTER` envelope (match_id=None) passes; valid `GAME_START` envelope passes.

### G3 — Unit tests for `Validation`
- [x] **G3.1** Create `tests/unit/services/protocol/test_validation.py`.
  - *DoD:* collected by pytest.
- [x] **G3.2** Test valid `REGISTER` envelope (match_id=None) passes without raising.
  - *DoD:* no exception.
- [x] **G3.3** Test valid non-REGISTER envelope (match_id set) passes without raising.
  - *DoD:* no exception.
- [x] **G3.4** Test wrong `protocol_version` raises `ProtocolVersionError`.
  - *DoD:* `expected="1.00"`, `envelope.protocol_version="0.90"` → `ProtocolVersionError`.
- [x] **G3.5** Test non-REGISTER envelope with `match_id=None` raises `ValidationError`.
  - *DoD:* `GAME_START` + `match_id=None` → `ValidationError`.
- [x] **G3.6** Test negative `seq` raises `ValidationError`.
  - *DoD:* `seq=-1` → `ValidationError`.
- [x] **G3.7** Test `REGISTER` with `match_id=None` AND correct version passes.
  - *DoD:* no exception raised.

---

## Module H — Package wiring

### H1 — Transport package `__init__.py`
- [x] **H1.1** Update `src/agent_arena/shared/transport/__init__.py` to export `Channel`, `InMemoryChannel`, `ConnectionClosedError`, `send_frame`, `recv_frame`, `FrameTooLargeError`, `TcpServer`, `TcpClient`, `ConnectionFailedError`.
  - *DoD:* `from agent_arena.shared.transport import Channel, TcpServer, TcpClient, send_frame, recv_frame` works.
- [x] **H1.2** Add `__all__` listing all exported names.
  - *DoD:* `__all__` is defined.

### H2 — Protocol package `__init__.py`
- [x] **H2.1** Update `src/agent_arena/services/protocol/__init__.py` to export all public names from all five protocol modules.
  - *DoD:* `from agent_arena.services.protocol import MessageType, Envelope, Codec, validate` works.
- [x] **H2.2** Verify no import in `shared/transport/` or `services/protocol/` pulls from `apps/` or `services/referee/` or `services/player/`.
  - *DoD:* `ruff check` clean; no circular import on `import agent_arena.services.protocol`.

---

## Module I — Quality gates

> PRD coverage: NL-AC8, NL-AC9, NL-AC10, NL-AC11

- [x] **I1** Run `ruff check src/agent_arena/shared/transport/ src/agent_arena/services/protocol/` — 0 violations.
  - *DoD:* exits with code 0.
- [x] **I2** Run `ruff check tests/unit/shared/transport/ tests/unit/services/protocol/` — 0 violations.
  - *DoD:* exits with code 0.
- [x] **I3** Confirm each new source file is ≤ 150 code lines (NL-AC10).
  - *DoD:* all files pass.
- [x] **I4** Run `uv run pytest tests/unit/shared/transport/ tests/unit/services/protocol/ --cov=src/agent_arena/shared/transport --cov=src/agent_arena/services/protocol --cov-report=term-missing`.
  - *DoD:* coverage ≥ 85 % for each module (NL-AC8).
- [x] **I5** Run full suite `uv run pytest` — 0 new failures.
  - *DoD:* all tests that pass before this phase continue to pass.
- [x] **I6** Manual smoke test: write a 20-line script that creates an `InMemoryChannel` pair, sends a `HEARTBEAT` envelope through `send_frame`/`recv_frame`, decodes it with `Codec`, and validates it with `Validation`. Confirm it completes without error.
  - *DoD:* script exits with code 0; matches full message path from PLAN §4.

---

## Requirement traceability matrix

| PRD Requirement | Covered by tasks              |
|-----------------|-------------------------------|
| FR-CH1          | A2.2, A2.3, A4.6              |
| FR-CH2          | A1.3, A3.4, A4.4              |
| FR-CH3          | A3.6, A4.2                    |
| FR-CH4          | A3.3, A4.5                    |
| FR-CH5          | A1.3, A3.4, A3.5              |
| FR-FR1          | B2.1, B2.2, B4.2              |
| FR-FR2          | B3.1, B3.4, B4.2              |
| FR-FR3          | B3.3, B4.4                    |
| FR-FR4          | B3.2, B3.4, B4.5              |
| FR-FR5          | B3.5, B4.6, B4.7              |
| FR-FR6          | B1.3, B4.4                    |
| FR-FR7          | B3.3 (no default in source)   |
| FR-SV1          | C3.1                          |
| FR-SV2          | C3.2, C4.2                    |
| FR-SV3          | C3.3, C4.2                    |
| FR-SV4          | C3.4, C4.3                    |
| FR-SV5          | C3.5, C4.5                    |
| FR-SV6          | C3.1 (params only)            |
| FR-CL1          | D2.1                          |
| FR-CL2          | D2.2, D2.3, D3.3              |
| FR-CL3          | D2.3, D3.3                    |
| FR-CL4          | D2.4                          |
| FR-CL5          | D2.5                          |
| FR-CL6          | D1.3                          |
| FR-CL7          | D2.1 (params only)            |
| FR-MT1          | E1.3                          |
| FR-MT2          | E1.3, E1.5                    |
| FR-MT3          | H2.1                          |
| FR-EN1          | E2.3                          |
| FR-EN2          | E2.4, E2.6                    |
| FR-EN3          | E2.3 (type annotation only)   |
| FR-EN4          | E2.3 (payload: dict)          |
| FR-PL1–FR-PL11  | E3.3, E3.4, E3.6              |
| FR-CO1          | F2.1, F2.2, F2.3, F4.2        |
| FR-CO2          | F3.1, F3.5, F4.2              |
| FR-CO3          | F4.2                          |
| FR-CO4          | F3.2, F4.3                    |
| FR-CO5          | F3.3, F4.4                    |
| FR-CO6          | F1.3, F4.3                    |
| FR-CO7          | F3.1 (no payload inspection)  |
| FR-VA1          | G2.1                          |
| FR-VA2          | G2.2, G3.4                    |
| FR-VA3          | G2.3                          |
| FR-VA4          | G2.4, G3.5                    |
| FR-VA5          | G2.5, G3.6                    |
| FR-VA6          | G1.3                          |
| FR-VA7          | G2.1 (no payload check)       |
| NL-AC1          | I6                            |
| NL-AC2          | B4.5                          |
| NL-AC3          | B4.4                          |
| NL-AC4          | G3.4                          |
| NL-AC5          | G3.4 (type check)             |
| NL-AC6          | C4.3                          |
| NL-AC7          | D3.3                          |
| NL-AC8          | I4                            |
| NL-AC9          | I1, I2                        |
| NL-AC10         | I3                            |
| NL-AC11         | B3.3, D2.4 (config-sourced)   |
