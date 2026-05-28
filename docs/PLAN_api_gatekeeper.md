# Architecture Plan — API Gatekeeper Subsystem

| Field    | Value                                      |
|----------|--------------------------------------------|
| Document | `PLAN_api_gatekeeper.md`                   |
| Project  | `agent-arena`                              |
| Version  | 1.00                                       |
| Date     | 2026-05-28                                 |
| Status   | Draft                                      |

> Companion: [PRD_api_gatekeeper.md](PRD_api_gatekeeper.md) · [TODO_api_gatekeeper.md](TODO_api_gatekeeper.md)
> No source code in this document — structure, interfaces in prose, and diagrams only.

---

## 1. Overview

One new module is added to `shared/`. It is entirely independent of game logic,
transport, and protocol — it only knows about *outbound LLM calls*. Every process
(referee or player) constructs one instance at startup and threads it into the
`LLMClient` facade.

```
shared/
├── api_gatekeeper.py   ← APIGatekeeper + exception classes
├── llm_client.py       ← (modified) backends call gatekeeper.gate(...)
├── config.py           ← (modified) adds GatekeeperConfig
├── shutdown.py         (existing — unchanged)
├── watchdog.py         (existing — unchanged)
└── heartbeat.py        (existing — unchanged)
```

How it collaborates with the rest of the system:

```
                ┌─────────────────────────────────────────────────────┐
                │                Any process (referee or player)       │
                │                                                      │
  Brain / Judge │   LLMClient ──► backend ──► APIGatekeeper.gate()    │
  callsite      │                                  │                   │
                │                                  ▼                   │
                │                  ┌────────────────────────────┐     │
                │                  │  token bucket (RPM)        │     │
                │                  │  hard counter (RPD)        │     │
                │                  │  semaphore (concurrency)   │     │
                │                  │  breaker state machine     │     │
                │                  └────────────────────────────┘     │
                │                                  │                   │
                │                                  ▼                   │
                │              gRPC / subprocess to Gemini             │
                └─────────────────────────────────────────────────────┘
```

---

## 2. The Four Layers of LLM Defense (Updated)

Each layer catches what the previous one misses.

| Layer | Mechanism                            | Catches                                   | Configured by                            |
|-------|--------------------------------------|-------------------------------------------|------------------------------------------|
| 0     | Per-call retry + backoff + jitter    | Single-call transient 5xx                 | `_MAX_RETRIES` / `_MAX_BACKOFF_SECONDS` in `llm_client.py` |
| 1     | **APIGatekeeper rate limit (RPM/RPD)** | Quota ceilings hit by concurrent callers  | `config.llm.gatekeeper.rpm` / `.rpd`    |
| 2     | **APIGatekeeper concurrency cap**      | Thundering herd of parallel calls         | `config.llm.gatekeeper.max_concurrency` |
| 3     | **APIGatekeeper circuit breaker**      | Sustained upstream outage (> retry budget) | `config.llm.gatekeeper.breaker_*`       |
| 4     | Match-termination outcome propagation| Silent forfeit laundering                 | `terminated_reason = "quota_aborted"`   |

Layer 0 is preserved as-is. Layers 1–3 live entirely inside `APIGatekeeper`.
Layer 4 is referee + `print_transcript` plumbing.

---

## 3. Building Blocks

### 3.1 `APIGatekeeper`

- **Setup:** instantiated once per process at startup, immediately after config load and `ShutdownCoordinator`.
- **Input:** `gate(timeout=...)` context-manager entry from `llm_client` backends, one call per outbound LLM request.
- **Output:**
  - Blocks until a token + concurrency slot are available (or raises one of four exception types).
  - Records outcome (`success` / `retryable_error` / `fatal_error`) on context-manager exit.
  - Maintains the breaker state machine and the daily counter.
- **Key invariants:**
  - At most `max_concurrency` callers are inside the `with` block simultaneously.
  - At most `rpm` successful entries occur in any 60-second window.
  - At most `rpd` total entries occur per UTC day.
  - Once the breaker transitions to OPEN, no new caller enters until cooldown elapses and a HALF_OPEN probe is decided.
- **Used by:** `GoogleGenAIClient._generate`, `GeminiCLIClient._run`. Nothing else in the codebase calls it directly.

### 3.2 Exception hierarchy

```
GatekeeperError
 ├── GatekeeperOpenError         (breaker is OPEN)
 ├── GatekeeperExhaustedError    (RPD budget consumed)
 └── GatekeeperTimeoutError      (acquire timed out waiting for tokens / slot)
```

These four propagate up unchanged through `LLMClient.generate_json` / `generate_text`
so the referee and player can branch on them without parsing `LLMError` strings.

---

## 4. Internal State Model

| Component                       | Owner             | Protected by                | Updated on            |
|---------------------------------|-------------------|-----------------------------|-----------------------|
| `_tokens: float` (RPM bucket)   | `APIGatekeeper`   | `_lock` + `_cond`           | `acquire`, refill tick |
| `_rpd_remaining: int`           | `APIGatekeeper`   | `_lock`                     | `acquire`, midnight reset |
| `_rpd_reset_at: datetime`       | `APIGatekeeper`   | `_lock`                     | construction, midnight reset |
| `_in_flight: int`               | `APIGatekeeper`   | `_lock`                     | `acquire`, `release`  |
| `_breaker_state: enum`          | `APIGatekeeper`   | `_lock`                     | `release`, cooldown timer check |
| `_consecutive_failures: int`    | `APIGatekeeper`   | `_lock`                     | `release`             |
| `_opened_at: float | None`      | `APIGatekeeper`   | `_lock`                     | CLOSED→OPEN transition |
| `_half_open_probe_in_flight`    | `APIGatekeeper`   | `_lock`                     | OPEN→HALF_OPEN, probe release |

All state is in-memory only. A process restart resets everything.

---

## 5. Acquire / Release Flow

### 5.1 Happy path (CLOSED, budget available, slot free)

```
caller: with gatekeeper.gate(timeout=180):
  → acquire():
      lock:
        if breaker == OPEN: raise GatekeeperOpenError
        if rpd_remaining == 0: raise GatekeeperExhaustedError
        refill tokens based on elapsed
        wait on _cond while (tokens < 1 or in_flight >= max_concurrency)
            (uses cond.wait_for with timeout = acquire_timeout)
        tokens -= 1
        rpd_remaining -= 1
        in_flight += 1
        if breaker == HALF_OPEN: half_open_probe_in_flight = True
      unlock
  → caller does its HTTP/subprocess call
  → release(outcome="success"):
      lock:
        in_flight -= 1
        if breaker == HALF_OPEN and probe was this caller:
            breaker = CLOSED; consecutive_failures = 0
        elif breaker == CLOSED:
            consecutive_failures = 0
        _cond.notify_all()
      unlock
```

### 5.2 Breaker trip (CLOSED → OPEN)

```
caller: with gatekeeper.gate(...):
  → acquire() succeeds (still CLOSED)
  → caller's HTTP returns 503; backend's internal retries also fail
  → release(outcome="retryable_error"):
      lock:
        in_flight -= 1
        consecutive_failures += 1
        if consecutive_failures >= breaker_threshold
           and (now - first_failure_in_window) <= breaker_window_seconds:
            breaker = OPEN
            opened_at = now
            log WARNING "breaker tripped"
        _cond.notify_all()  ← so any acquire-waiters fail fast next loop
```

### 5.3 Cooldown → HALF_OPEN → CLOSED

```
caller: with gatekeeper.gate(...):
  → acquire():
      lock:
        if breaker == OPEN:
            if (now - opened_at) >= breaker_cooldown_seconds:
                breaker = HALF_OPEN
                half_open_probe_in_flight = False
            else:
                raise GatekeeperOpenError
        if breaker == HALF_OPEN and half_open_probe_in_flight:
            raise GatekeeperOpenError  ← only one probe at a time
        ... rest of acquire ...
  → caller's HTTP succeeds
  → release(outcome="success"):
      lock:
        breaker = CLOSED
        consecutive_failures = 0
        half_open_probe_in_flight = False
```

---

## 6. File Structure

```
src/agent_arena/shared/
├── __init__.py             ← (modified) re-export APIGatekeeper + exceptions
├── api_gatekeeper.py       ← APIGatekeeper + GatekeeperError + 3 subclasses (NEW)
├── llm_client.py           ← (modified) backends call gatekeeper.gate(...)
├── config.py               ← (modified) adds GatekeeperConfig under LLMConfig
├── shutdown.py             (existing — unchanged)
├── watchdog.py             (existing — unchanged)
├── heartbeat.py            (existing — unchanged)
└── ... rest unchanged

src/agent_arena/apps/
├── referee_app.py          ← (modified) builds gatekeeper, branches on quota_aborted
├── player_app.py           ← (modified) builds gatekeeper, brain catches gatekeeper errors
└── run_helpers.py          ← (modified) print_transcript adds API state + banner

src/agent_arena/services/referee/
└── _turn_runner.py         ← (modified) recognize flag="quota_aborted" alongside "timeout"

config/
└── setup.json              ← (modified) adds llm.gatekeeper block

tests/unit/shared/
└── test_api_gatekeeper.py  ← (NEW)

tests/integration/
└── test_quota_aborted_verdict.py ← (NEW) end-to-end: 503 storm → verdict labels quota_aborted
```

---

## 7. Thread Model

The gatekeeper itself owns no thread. It is purely synchronous: every method
runs on the caller's thread, using one `threading.Lock` + one `threading.Condition`.

Callers — that is, the existing brain worker thread inside each player and the
judge thread inside the referee — already exist (see [PLAN_fault_tolerance.md](PLAN_fault_tolerance.md) §4).
They simply add a `with gatekeeper.gate(...):` around the LLM call.

There is no new daemon thread, no background refill loop. The token bucket
refills lazily inside `acquire` by computing `elapsed * (rpm / 60)` since the
last refill timestamp.

---

## 8. Architecture Decision Records

| ADR        | Decision                                                                  | Rationale                                                                                       | Trade-off                                            |
|------------|---------------------------------------------------------------------------|-------------------------------------------------------------------------------------------------|------------------------------------------------------|
| GK-001     | One `APIGatekeeper` per process, injected, no module-level singleton      | Avoids hidden global; mirrors how `ShutdownCoordinator` is wired                                | Caller must remember to inject (caught by tests)     |
| GK-002     | Gatekeeper sits OUTSIDE existing per-call retry loop, not inside          | Preserves working jitter/backoff in [llm_client.py](../src/agent_arena/shared/llm_client.py); the new layer only adds budget + breaker | One retried call still counts as one RPM token (correct — only one request actually reaches the wire at a time per caller) |
| GK-003     | Per-process budgets, no IPC                                               | Three processes share an upstream quota at Google. Operator splits `rpm` in `setup.json` (e.g. `rpm/3`); no coordination overhead. | Slight under-utilization vs. shared budget — acceptable |
| GK-004     | Token bucket for RPM, hard counter for RPD                                | Bucket smooths intra-minute bursts; daily is a hard ceiling, not a rate                          | RPD does NOT smooth — exhaustion is an immediate error |
| GK-005     | Breaker counts `retryable_error` only                                     | A schema-violation 200 is not capacity pressure                                                  | A flood of malformed JSON would not trip breaker — correct behavior |
| GK-006     | `quota_aborted` is a first-class match-termination reason                 | Direct response to 2026-05-28 silent-forfeit incident                                            | Adds one new branch in referee + verdict surfacing   |
| GK-007     | Lazy token refill in `acquire` (no background thread)                     | Zero new daemon threads; aligns with FT layer's principle of minimal threads                     | A long idle period accumulates capacity (capped at `rpm`) |
| GK-008     | RPD resets at UTC midnight                                                | Matches Google's quota window for paid Gemini Flash                                              | Process restart in the middle of a day re-grants full quota; acceptable in-scope per §11 of PRD |
| GK-009     | HALF_OPEN allows exactly one probe                                        | Standard breaker pattern; prevents thundering-herd on cooldown expiry                            | Probe owner is racy under contention — acceptable (any caller is a fine probe) |

---

## 9. Integration Checklist (wiring, not coding)

When the referee or player is being modified, the following wiring must be done —
in this order:

1. Load `config.llm.gatekeeper` from `setup.json`.
2. Instantiate `APIGatekeeper(**config.llm.gatekeeper.model_dump())`.
3. Pass `gatekeeper=...` into `LLMClient(provider=..., gatekeeper=gatekeeper)`.
4. In the referee, register a shutdown callback that logs `gatekeeper.snapshot()` for postmortem.
5. In the player brain, wrap LLM calls in `try: ... except GatekeeperError as e: submit MOVE_SUBMIT(flag="quota_aborted", reason=str(e))`.
6. In `_turn_runner.py`, treat `flag="quota_aborted"` as a terminal match condition, not a per-turn forfeit.
7. In `print_transcript`, render the gatekeeper snapshot and the loud banner when any turn carries `flag="quota_aborted"`.

---

## 10. Test Strategy

| Layer            | Test file                                | What it asserts                                                              |
|------------------|------------------------------------------|------------------------------------------------------------------------------|
| Unit             | `tests/unit/shared/test_api_gatekeeper.py` | Token bucket math, concurrency cap, RPD counter, breaker FSM, exceptions      |
| Integration      | `tests/integration/test_quota_aborted_verdict.py` | Inject a fake 503-storm backend; assert verdict JSON carries `terminated_reason = "quota_aborted"` and transcript prints banner |
| Existing suite   | `tests/`                                 | 0 regressions — all prior tests still pass                                   |

Unit tests use a *fake clock* injected via constructor parameter (default
`time.monotonic`) so timing-sensitive tests are deterministic. The fake clock
is the only constructor parameter beyond the six config-driven ones; it
defaults to `time.monotonic`, so production code passes nothing.

---

## 11. Risks & Mitigations

| Risk                                                                  | Mitigation                                                                                  |
|-----------------------------------------------------------------------|---------------------------------------------------------------------------------------------|
| `acquire_timeout` too short → spurious `GatekeeperTimeoutError`        | Default 180 s in `setup.json`; operator-tunable                                             |
| Operator misconfigures `rpm=0`                                         | `GatekeeperConfig` Pydantic validator rejects non-positive values                            |
| Breaker traps system in OPEN forever                                  | `breaker_cooldown_seconds` always elapses; HALF_OPEN guarantees a probe                     |
| `quota_aborted` flag conflicts with existing `timeout` flag handling   | `_turn_runner.py` change is additive: new branch, existing `timeout` path untouched         |
| Gatekeeper accidentally bypassed by a new callsite                    | Test `test_no_direct_genai_calls.py`: greps codebase for `client.models.generate_content` outside `llm_client.py` |
