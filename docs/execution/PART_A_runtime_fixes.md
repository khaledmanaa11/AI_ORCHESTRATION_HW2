# PART A — Runtime safety & small fixes

Small, self-contained, no cross-part dependencies. Do them in order. Each ends green + pushed.

---

## A1 — Enforce `validate()` on inbound REGISTER + typed error
**Goal:** The referee must reject a wrong-protocol-version or wrong-type first message with a
typed `ERROR`, instead of silently accepting it.
**Why:** `REMAINING_WORK.md` §3, §9, §10 — `validate()` exists but is never called.
**Read first:**
- `src/agent_arena/services/protocol/validation.py` (≈ lines 5–31: `validate`, `ProtocolVersionError`, `UnknownMessageTypeError`)
- `src/agent_arena/services/protocol/message_types.py` (≈ 4–16)
- `src/agent_arena/services/referee/server.py` (≈ 60–135: `on_connect`, `decode`, `_send_error`)
- `src/agent_arena/constants.py` (PROTOCOL_VERSION at line 5)
**Files (scope):** `services/protocol/message_types.py`, `services/referee/server.py`. (Add the enum in message_types.)
**Do:**
1. Add an `ErrorCode` enum to `message_types.py` with at least: `VERSION_MISMATCH`,
   `MALFORMED_MESSAGE`, `UNKNOWN_TYPE`, `UNEXPECTED_MESSAGE`. Make it `class ErrorCode(str, Enum)`
   to match the existing `MessageType(str, Enum)` style. Export it in `protocol/__init__.py`.
2. In `server.py` `on_connect`, immediately after `env = decode(raw)`, call
   `validate(env, PROTOCOL_VERSION)` inside a `try`. On `ProtocolVersionError` send an `ERROR`
   envelope with `code=ErrorCode.VERSION_MISMATCH`, then close the connection and return. On
   `UnknownMessageTypeError`/`ValidationError` send `ErrorCode.MALFORMED_MESSAGE` and close.
3. Replace the existing bare `"MALFORMED_MESSAGE"` string (if present) with `ErrorCode.MALFORMED_MESSAGE`.
**Verify:**
```
uv run ruff check <files-you-changed>
uv run pytest tests/unit/services/protocol -q
uv run pytest tests/unit/services/referee -q
```
Then add ONE test in `tests/unit/services/protocol/test_validation.py` (or referee) asserting a
version-mismatch envelope makes `validate` raise `ProtocolVersionError`. All green.
**Commit:** `fix(protocol): enforce validate() on REGISTER and send typed error codes`

---

## A2 — Send `ERROR` before closing the 3rd+ connection
**Goal:** When a third client connects to a full match, send it an `ERROR` (capacity) before
closing, instead of a silent socket close.
**Why:** `REMAINING_WORK.md` §9 — PRD §3 requires a typed error; code closes silently.
**Read first:**
- `src/agent_arena/shared/transport/tcp_server.py` (≈ 32–95: accept loop, `_reject_extras`, lines 83–90)
- `src/agent_arena/services/referee/server.py` (how `_send_error`/ERROR envelopes are built)
**Files (scope):** `shared/transport/tcp_server.py` (and import the codec/protocol only if a clean seam exists; if transport must stay protocol-free, instead pass a small `on_reject` callback the referee supplies — choose the option that keeps `import socket` out of services and protocol out of transport).
**Do:**
1. Before closing an over-capacity socket, write one framed `ERROR` message with a capacity
   code (reuse `ErrorCode` from A1; add `MATCH_FULL`). Keep transport layering clean — if
   building a protocol envelope inside transport is wrong, add an `on_reject(sock)` hook called
   by the server and let the referee fill it.
2. Then close as before.
**Verify:**
```
uv run ruff check <files-you-changed>
uv run pytest tests/unit/shared/transport/test_tcp_server.py -q
```
Add/extend a test asserting a 3rd connection receives a frame before EOF.
**Commit:** `fix(transport): send ERROR to over-capacity client before closing`

---

## A3 — Use `PROTOCOL_VERSION` constant in player agent
**Goal:** Stop hardcoding the protocol version.
**Why:** `REMAINING_WORK.md` §3 — `"1.00"` is hardcoded at `player/agent.py:53`.
**Read first:**
- `src/agent_arena/services/player/agent.py` (≈ line 53)
- `src/agent_arena/constants.py` (line 5: `PROTOCOL_VERSION`)
**Files (scope):** `services/player/agent.py`.
**Do:** Add `from agent_arena.constants import PROTOCOL_VERSION` and replace the literal
`"1.00"` with `PROTOCOL_VERSION` where the envelope's `protocol_version` is set.
**Verify:**
```
uv run ruff check <files-you-changed>
uv run pytest tests/unit/services/player -q
```
**Commit:** `refactor(player): use PROTOCOL_VERSION constant instead of literal`

---

## A4 — Narrow `TcpClient.connect` except clause
**Goal:** Only retry on genuinely retryable connection errors; let host-not-found fail fast.
**Why:** `REMAINING_WORK.md` §3 — broad `except OSError` masks non-retryable errors.
**Read first:** `src/agent_arena/shared/transport/tcp_client.py` (≈ 12–63, the retry loop ~line 40).
**Files (scope):** `shared/transport/tcp_client.py`.
**Do:** Change the retry `except OSError` to `except (ConnectionRefusedError, TimeoutError)`.
Anything else should propagate as `ConnectionFailedError` (or the existing failure type) without
consuming retry attempts.
**Verify:**
```
uv run ruff check <files-you-changed>
uv run pytest tests/unit/shared/transport/test_tcp_client.py -q
```
Add a test: a non-retryable error (e.g. `gaierror`/generic `OSError`) is NOT retried.
**Commit:** `fix(transport): only retry connect on refused/timeout, not all OSError`

---

## A5 — Config-drive retry + frame-size params
**Goal:** Remove hardcoded `5` retries, `0.1` backoff, and the default `max_frame_size` in the
player path; read them from config.
**Why:** `REMAINING_WORK.md` §3 — `NetworkConfig` is missing fields; FramedChannel uses a hardcoded default.
**Read first:**
- `src/agent_arena/shared/config.py` (≈ 9–27: `NetworkConfig`, `FramingConfig`)
- `src/agent_arena/services/player/client.py` (≈ 23–24 hardcoded defaults; ≈ 49 FramedChannel construction)
- `config/setup.json` (the live config file — add fields here too)
**Files (scope):** `shared/config.py`, `services/player/client.py`, `config/setup.json`.
**Do:**
1. Add `max_retries: int` and `backoff_base: float` to `NetworkConfig` (with the current
   defaults 5 and 0.1 as the field defaults).
2. In `PlayerClient`, read both from config instead of literals.
3. Pass `config.framing.max_frame_size_bytes` to `FramedChannel(...)` at construction.
4. Add the two new keys under the network block in `config/setup.json`.
**Verify:**
```
uv run ruff check <files-you-changed>
uv run pytest tests/unit/shared/test_config.py tests/unit/services/player -q
```
**Commit:** `fix(config): drive retry/backoff/frame-size from config, not literals`

---

## A6 — De-duplicate `TERMINATED_*` constants
**Goal:** One source of truth for termination tokens.
**Why:** `REMAINING_WORK.md` §5 — `result.py` re-declares constants already in `constants.py`.
**Read first:**
- `src/agent_arena/services/referee/result.py` (≈ 11–12, the duplicate declarations)
- `src/agent_arena/constants.py` (≈ 43–44, the originals)
**Files (scope):** `services/referee/result.py` (and any file importing the tokens *from* result.py — fix those imports).
**Do:** Delete the local `TERMINATED_DISCONNECT`/`TERMINATED_ABORTED` in `result.py`; import them
from `agent_arena.constants`. Update any importers that pulled them from `result`.
**Verify:**
```
uv run ruff check <files-you-changed>
uv run pytest -q
```
**Commit:** `refactor(referee): single source for TERMINATED_* constants`
