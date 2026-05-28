# PRD — API Gatekeeper Subsystem

| Field       | Value                                                |
|-------------|------------------------------------------------------|
| Document    | `PRD_api_gatekeeper.md`                              |
| Project     | `agent-arena`                                        |
| Version     | 1.00                                                 |
| Date        | 2026-05-28                                           |
| Status      | Draft — pending approval before development          |
| Author      | Khaled                                               |

> Companion documents: [PLAN_api_gatekeeper.md](PLAN_api_gatekeeper.md) · [TODO_api_gatekeeper.md](TODO_api_gatekeeper.md)
> Parent plan: [PLAN.md](PLAN.md) · [PRD.md](PRD.md)
> Motivating incident: [devlog/2026-05-28-503-storm-silent-forfeit.md](devlog/2026-05-28-503-storm-silent-forfeit.md)

---

## 1. Purpose & Scope

This document specifies the **API Gatekeeper** subsystem of `agent-arena`. Its sole
responsibility is being the **single chokepoint for every outbound LLM call** made
by any process in the system (referee judge, player brains, best-of-N expansions).

It enforces:

1. A **global RPM and RPD budget** across all concurrent callers in the process.
2. A **concurrency cap** so N callers cannot fan out into N parallel HTTPS requests.
3. A **circuit breaker** that opens after sustained upstream failures and fails fast
   instead of letting each caller burn its own retry budget in parallel.
4. A **distinct exhaustion outcome** that propagates to the referee verdict so
   capacity failures cannot be silently laundered into a player forfeit (the exact
   failure documented in the 2026-05-28 devlog).

This PRD covers exactly one new shared module and the minimum integration changes
needed to route every existing LLM call through it.

| Module                          | Class             | Lives in   |
|---------------------------------|-------------------|------------|
| `shared/api_gatekeeper.py`      | `APIGatekeeper`   | `shared/`  |

Everything else — game logic, transport, protocol, brains, judge — is out of scope
for this document except where it must call into the gatekeeper.

---

## 2. Problem Statement

Without a gatekeeper, the system has the following failure modes — all of which
were observed or are reachable from observed behavior:

| Failure                                       | Current effect (no gatekeeper)                                     |
|-----------------------------------------------|--------------------------------------------------------------------|
| Capacity 503 storm > 2 min                    | Each caller exhausts retries independently → silent forfeit cascade |
| Two players + judge call API concurrently     | 3× parallel HTTPS hits — no shared awareness of upstream pressure  |
| best_of_N=3 with 2 players                    | Up to 6 parallel calls per turn — synchronized retries on a 503    |
| Paid-tier RPM/RPD ceiling hit mid-match       | Per-call 429s, scattered retries, no clean abort path              |
| Capacity exhaustion vs. real player forfeit   | Indistinguishable in the verdict JSON                              |

The root cause: **every LLM call is independent, sees only its own retries, and
has no notion of a shared budget or a shared circuit state**.

---

## 3. Goals

| ID     | Goal                                                                                          |
|--------|-----------------------------------------------------------------------------------------------|
| GK-G1  | Every outbound LLM call (both backends) is routed through one `APIGatekeeper` instance        |
| GK-G2  | A configured global RPM and RPD budget is never exceeded across all concurrent callers        |
| GK-G3  | Concurrent in-flight calls never exceed the configured `max_concurrency`                      |
| GK-G4  | Sustained upstream failure trips a circuit breaker that fails new calls fast                  |
| GK-G5  | Capacity exhaustion produces a verdict outcome distinguishable from a player forfeit          |
| GK-G6  | Existing per-call retry/backoff logic in `llm_client.py` is preserved, not duplicated         |
| GK-G7  | The gatekeeper has no knowledge of debate, game logic, players, or judge — only LLM I/O       |
| GK-G8  | The gatekeeper is thread-safe and is the **only** module that throttles LLM traffic           |

---

## 4. Acceptance Criteria

| ID       | Criterion                                                                                              | Target |
|----------|--------------------------------------------------------------------------------------------------------|--------|
| GK-AC1   | With `rpm=2` and 3 concurrent callers, no minute window ever observes > 2 successful starts            | Pass   |
| GK-AC2   | With `max_concurrency=1`, two concurrent `acquire()` calls serialize (one waits for the other)         | Pass   |
| GK-AC3   | Sustained 503 responses for K consecutive calls within window W trip the breaker; subsequent calls raise `GatekeeperOpenError` immediately | Pass   |
| GK-AC4   | After cooldown `C`, the breaker enters half-open and a single probe call is permitted                  | Pass   |
| GK-AC5   | Quota-exhausted matches surface in the verdict JSON with a distinct `terminated_reason` (not "forfeit") | Pass   |
| GK-AC6   | `print_transcript` from `apps/run_helpers.py` prints a loud banner when the match was quota-aborted    | Pass   |
| GK-AC7   | Both `GoogleGenAIClient` and `GeminiCLIClient` route through the gatekeeper — verified by tests        | Pass   |
| GK-AC8   | Gatekeeper module is ≤ 200 code lines                                                                  | Pass   |
| GK-AC9   | Test coverage for `api_gatekeeper.py` ≥ 85 %                                                           | Pass   |
| GK-AC10  | `ruff check` reports 0 violations on the new file and all new tests                                    | Pass   |
| GK-AC11  | No timeout / RPM / RPD / breaker value is hardcoded in source — all come from config                   | Pass   |
| GK-AC12  | Full existing test suite continues to pass with 0 regressions                                          | Pass   |

---

## 5. Functional Requirements

### 5.1 `APIGatekeeper` (`shared/api_gatekeeper.py`)

**Purpose:** single, thread-safe authority for "may this LLM call proceed now,
and what was its outcome." Wraps a token-bucket rate limiter, a semaphore, a
circuit breaker, and outcome bookkeeping in one object.

| ID       | Requirement                                                                                                                                |
|----------|--------------------------------------------------------------------------------------------------------------------------------------------|
| FR-GK1   | Constructor: `__init__(self, rpm: int, rpd: int, max_concurrency: int, breaker_threshold: int, breaker_window_seconds: float, breaker_cooldown_seconds: float) -> None`. |
| FR-GK2   | No default values for any of the six constructor parameters. All must come from config.                                                    |
| FR-GK3   | Expose `acquire(self, *, timeout: float | None = None) -> None`. Blocks until (a) a token is available from the per-minute bucket, (b) the per-day budget has room, AND (c) a concurrency slot is free. |
| FR-GK4   | `acquire` must raise `GatekeeperOpenError` immediately (without waiting) if the breaker is currently OPEN.                                |
| FR-GK5   | `acquire` must raise `GatekeeperExhaustedError` immediately if the per-day budget (RPD) has already been fully consumed.                  |
| FR-GK6   | `acquire` honors `timeout`: if the caller cannot enter within `timeout` seconds, raises `GatekeeperTimeoutError`.                          |
| FR-GK7   | Expose `release(self, *, outcome: Literal["success", "retryable_error", "fatal_error"]) -> None`. Releases the concurrency slot and updates breaker state. |
| FR-GK8   | Provide a context manager `gate(self, *, timeout: float | None = None) -> Iterator[OutcomeRecorder]` that wraps `acquire`/`release` so callers cannot leak slots. |
| FR-GK9   | Token-bucket: refills at `rpm / 60.0` tokens per second; capacity = `rpm`. Initial bucket starts full.                                     |
| FR-GK10  | Daily counter resets at the next UTC midnight boundary after `__init__` time. After reset, `acquire` is again permitted up to `rpd`.       |
| FR-GK11  | Circuit breaker states: CLOSED → OPEN → HALF_OPEN → CLOSED. Transitions:                                                                  |
|          | • CLOSED → OPEN: when `breaker_threshold` consecutive `retryable_error` releases occur within `breaker_window_seconds`.                    |
|          | • OPEN → HALF_OPEN: after `breaker_cooldown_seconds` elapsed since last OPEN transition.                                                   |
|          | • HALF_OPEN → CLOSED: on the next `success` release.                                                                                       |
|          | • HALF_OPEN → OPEN: on the next `retryable_error` or `fatal_error` release.                                                                |
| FR-GK12  | While OPEN, only the cooldown timer can change state. Concurrent `acquire` calls all raise `GatekeeperOpenError`.                          |
| FR-GK13  | While HALF_OPEN, exactly ONE `acquire` is permitted to proceed; all others raise `GatekeeperOpenError` until that probe releases.          |
| FR-GK14  | Thread-safe: all state transitions guarded by a single `threading.Lock`. No nested locks.                                                   |
| FR-GK15  | Logging: every state transition (CLOSED↔OPEN↔HALF_OPEN), every budget exhaustion, every concurrency wait > 1 s logged at WARNING.         |
| FR-GK16  | Expose `snapshot(self) -> dict` returning current state (`rpm_tokens`, `rpd_remaining`, `in_flight`, `breaker_state`, `consecutive_failures`) for tests and verdict propagation. |

### 5.2 Exception types

| ID       | Requirement                                                                                                          |
|----------|----------------------------------------------------------------------------------------------------------------------|
| FR-EX1   | Define `GatekeeperError(Exception)` as base class.                                                                  |
| FR-EX2   | Define `GatekeeperOpenError(GatekeeperError)` — circuit is open.                                                    |
| FR-EX3   | Define `GatekeeperExhaustedError(GatekeeperError)` — RPD budget consumed.                                           |
| FR-EX4   | Define `GatekeeperTimeoutError(GatekeeperError)` — could not acquire within `timeout`.                              |
| FR-EX5   | All four classes carry a `reason: str` attribute usable in the verdict outcome.                                     |

---

## 6. Integration Requirements

### 6.1 `shared/llm_client.py`

| ID         | Requirement                                                                                                                         |
|------------|-------------------------------------------------------------------------------------------------------------------------------------|
| FR-INT-L1  | `GoogleGenAIClient._generate` must wrap its `generate_content` call in `gatekeeper.gate(timeout=...)`.                              |
| FR-INT-L2  | `GeminiCLIClient._run` must wrap its `subprocess.run` call in `gatekeeper.gate(timeout=...)`.                                       |
| FR-INT-L3  | On success, the context manager records `outcome="success"`.                                                                        |
| FR-INT-L4  | On any HTTP status in `_RETRYABLE_STATUS` (or CLI stderr containing "429"/"quota"/"unavailable"/"retry"), record `"retryable_error"`. |
| FR-INT-L5  | On any other failure, record `"fatal_error"`.                                                                                       |
| FR-INT-L6  | The gatekeeper is constructed once per process and injected into both backend classes — backends never construct their own.         |
| FR-INT-L7  | `LLMClient.__new__` accepts an optional `gatekeeper: APIGatekeeper | None` parameter. If `None`, it constructs one from the loaded config. |
| FR-INT-L8  | When `acquire` raises `GatekeeperOpenError` or `GatekeeperExhaustedError`, `llm_client` re-raises it unchanged (does NOT wrap in `LLMError`). |
| FR-INT-L9  | Existing per-call retry/backoff inside the two backends is preserved unchanged. The gatekeeper is a layer *outside* the retry loop. |

### 6.2 Referee process

| ID         | Requirement                                                                                                                         |
|------------|-------------------------------------------------------------------------------------------------------------------------------------|
| FR-INT-R1  | The referee app constructs one `APIGatekeeper` at startup from `config.llm.gatekeeper`.                                             |
| FR-INT-R2  | The referee passes that gatekeeper into its `LLMClient` (judge brain).                                                              |
| FR-INT-R3  | If any judge call raises `GatekeeperOpenError` or `GatekeeperExhaustedError`, the referee terminates the match with `terminated_reason = "quota_aborted"` rather than counting it as a default judgement. |
| FR-INT-R4  | The verdict JSON written to `results/` includes the gatekeeper `snapshot()` under a new `api_state` key.                            |

### 6.3 Player process

| ID         | Requirement                                                                                                                         |
|------------|-------------------------------------------------------------------------------------------------------------------------------------|
| FR-INT-P1  | The player app constructs its own `APIGatekeeper` at startup from `config.llm.gatekeeper`. (Each process has its own — they are not shared across processes; see §10 ADR-GK-003.) |
| FR-INT-P2  | The player passes that gatekeeper into its `LLMClient`.                                                                             |
| FR-INT-P3  | When the player brain catches `GatekeeperOpenError` or `GatekeeperExhaustedError`, it submits a `MOVE_SUBMIT` carrying flag `"quota_aborted"` (NOT `"timeout"`), so the referee can distinguish the two. |

### 6.4 Referee verdict surfacing

| ID         | Requirement                                                                                                                         |
|------------|-------------------------------------------------------------------------------------------------------------------------------------|
| FR-INT-V1  | `apps/run_helpers.py:print_transcript` adds a section "API Gatekeeper" showing `rpd_remaining`, `breaker_state`, and total `quota_aborted` flags seen. |
| FR-INT-V2  | When ≥ 1 turn carries `flag="quota_aborted"`, `print_transcript` prints a loud red banner above the verdict warning the result is API-capacity-tainted. |

---

## 7. Configuration Requirements

A new block `llm.gatekeeper` is added to [setup.json](../config/setup.json) and to
the Pydantic model in [shared/config.py](../src/agent_arena/shared/config.py).

| ID         | Requirement                                                                                              |
|------------|----------------------------------------------------------------------------------------------------------|
| FR-CFG1    | New `GatekeeperConfig` Pydantic model with fields: `rpm: int`, `rpd: int`, `max_concurrency: int`, `breaker_threshold: int`, `breaker_window_seconds: float`, `breaker_cooldown_seconds: float`, `acquire_timeout_seconds: float`. |
| FR-CFG2    | All fields are required (no defaults inside `GatekeeperConfig`). Defaults live in `setup.json` only.    |
| FR-CFG3    | `LLMConfig` gains a field `gatekeeper: GatekeeperConfig`.                                               |
| FR-CFG4    | Default values in `setup.json` for the paid Gemini Flash tier (per [gemini_paid_tier memory](../memory/gemini_paid_tier.md)): `rpm=2000`, `rpd=10000`, `max_concurrency=8`, `breaker_threshold=5`, `breaker_window_seconds=30.0`, `breaker_cooldown_seconds=60.0`, `acquire_timeout_seconds=180.0`. |
| FR-CFG5    | Validation: `rpm > 0`, `rpd > 0`, `max_concurrency > 0`, `breaker_threshold > 0`, all window/cooldown/timeout values > 0. |
| FR-CFG6    | No literal value for any of these parameters appears in `api_gatekeeper.py` source.                     |

---

## 8. Non-Functional Requirements

| ID        | Requirement                                                                                              |
|-----------|----------------------------------------------------------------------------------------------------------|
| GK-NFR1   | Thread-safe: all state transitions are atomic under one lock. No nested locks.                          |
| GK-NFR2   | No busy-waiting: use `threading.Condition.wait(timeout)` for the token bucket, never `time.sleep` polling. |
| GK-NFR3   | No circular imports: `shared/api_gatekeeper.py` imports only from stdlib and `shared/`.                 |
| GK-NFR4   | All transitions and exhaustion events logged with reason (`logger.warning` / `logger.error`).            |
| GK-NFR5   | Monotonic clock (`time.monotonic`) for all interval timing; wall clock (`datetime.now(UTC)`) only for the RPD midnight reset boundary. |
| GK-NFR6   | The gatekeeper is the only synchronization point — backends do NOT add their own semaphores or sleeps. |

---

## 9. Exhaustive Outcome Catalog

| # | Scenario                                                      | Caller sees                       | Verdict surfacing                          |
|---|---------------------------------------------------------------|-----------------------------------|---------------------------------------------|
| 1 | Normal call within budget                                     | success                           | (none — normal verdict)                     |
| 2 | Brief 503 burst, < `breaker_threshold` failures               | retries inside backend succeed    | (none — normal verdict)                     |
| 3 | Sustained 503 burst trips breaker                             | `GatekeeperOpenError` after K     | verdict: `terminated_reason = "quota_aborted"`, banner in transcript |
| 4 | RPD budget exhausted mid-match                                | `GatekeeperExhaustedError`        | verdict: `terminated_reason = "quota_aborted"`, banner in transcript |
| 5 | RPM bucket empty, caller waits                                | success after wait (≤ acquire_timeout) | (none — normal verdict; WARN log if wait > 1 s) |
| 6 | RPM bucket empty, caller waits longer than `acquire_timeout`  | `GatekeeperTimeoutError`          | verdict: `terminated_reason = "quota_aborted"`, banner in transcript |
| 7 | Breaker OPEN, cooldown elapses, single probe succeeds         | success on probe, CLOSED          | (none — normal verdict)                     |
| 8 | Breaker OPEN, cooldown elapses, single probe fails            | probe caller sees retryable_error, breaker re-OPEN | next caller: `GatekeeperOpenError`; same surfacing as #3 |
| 9 | Player process exits cleanly mid-call (already covered by FT) | gatekeeper slot reclaimed via context manager `__exit__` | (none — FT layer handles)           |

---

## 10. Architecture Decision Records (preview — full list in PLAN)

| ADR        | Decision                                                          | Rationale                                                                         |
|------------|-------------------------------------------------------------------|-----------------------------------------------------------------------------------|
| GK-001     | Single gatekeeper instance per process, injected via constructor  | Avoids hidden globals; aligns with how `ShutdownCoordinator` is wired             |
| GK-002     | Gatekeeper is OUTSIDE the existing retry loop, not inside         | Preserves working backoff/jitter logic; new layer only enforces budget + breaker  |
| GK-003     | Per-process budgets, not cross-process                            | The three processes already share an upstream quota at Google; per-process slicing of `rpm/3` lives in `setup.json`, kept simple |
| GK-004     | Token bucket for RPM, hard counter for RPD                        | Token bucket smooths bursts within a minute; daily is a hard ceiling, not a rate  |
| GK-005     | Breaker counts `retryable_error` only, not `fatal_error`          | A schema-violation 200 is not capacity pressure; only treat 5xx/429/quota as signal |
| GK-006     | `quota_aborted` is a first-class match-termination reason         | Direct response to the 2026-05-28 silent-forfeit incident; cannot be confused with a forfeit |

---

## 11. Out of Scope

- Cross-process / cross-machine gatekeeper coordination (single process only)
- Persisting RPD counters across process restarts (in-memory only — fresh start = fresh budget)
- Adaptive RPM tuning based on observed 429s (operator changes `setup.json`)
- Multiple upstream providers with separate budgets (one budget, both backends share)
- Replaying or queuing calls that hit `GatekeeperOpenError` (caller fails fast — match ends)
