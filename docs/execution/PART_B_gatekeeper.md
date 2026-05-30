# PART B — API Gatekeeper integration

The `APIGatekeeper` class is fully built and works, but **nothing uses it end-to-end**. This
part wires it into the referee, the player, the turn loop, and the transcript, then tests it.
Reference: `REMAINING_WORK.md` §1. Do steps in order (B2/B3/B4 build on B1).

---

## B1 — Wire `APIGatekeeper` into the referee + verdict
**Goal:** The referee builds one `APIGatekeeper` from config, injects it into its `LLMClient`,
catches `GatekeeperError`, and records `api_state` in the match verdict.
**Read first:**
- `src/agent_arena/shared/api_gatekeeper.py` (`APIGatekeeper`, `gate()`, `snapshot()`, `GatekeeperError`, ≈ 63–248)
- `src/agent_arena/shared/llm_client.py` (≈ 19, 69–101, 132–176 — how it accepts a gatekeeper)
- `src/agent_arena/shared/config.py` (≈ 28–60 — `GatekeeperConfig`, `LLMConfig.gatekeeper`)
- `src/agent_arena/apps/referee_app.py` (the `main()` wiring — currently builds `LLMClient` with no gatekeeper)
- `src/agent_arena/services/referee/result.py` and `game_loop.py` (where the verdict dict is assembled)
**Files (scope):** `apps/referee_app.py`, `services/referee/game_loop.py` (or `result.py` — wherever the verdict is built).
**Do:**
1. In `referee_app.main`, construct `gatekeeper = APIGatekeeper(**config.llm.gatekeeper.model_dump())`
   (confirm the exact field names by reading `GatekeeperConfig`).
2. Pass `gatekeeper=gatekeeper` into the `LLMClient(...)` the referee creates. (Read the
   `LLMClient` constructor to see the exact kwarg.)
3. When the match ends, add `api_state = gatekeeper.snapshot()` into the verdict dict under key
   `"api_state"`.
4. Wrap the match run so a `GatekeeperError` (e.g. `GatekeeperExhaustedError`) produces a verdict
   tagged `terminated_reason="quota_aborted"` plus `api_state` — do not crash the process.
**Verify:**
```
uv run ruff check src tests
uv run pytest tests/integration/test_debate_loop.py -q
```
Manually confirm a produced verdict (or a new small test) contains an `api_state` key.
**Commit:** `feat(referee): inject APIGatekeeper and record api_state in verdict`

---

## B2 — `quota_aborted` branch in the turn loop
**Goal:** When a `MOVE_SUBMIT` arrives carrying `flag="quota_aborted"` (the player ran out of
quota), the referee ends the match cleanly instead of treating it as a normal/retryable move.
**Read first:**
- `src/agent_arena/services/referee/_turn_runner.py` (≈ 89–155 — the move-handling branches)
- `src/agent_arena/services/referee/game_loop.py` (how a terminated match is finalized)
- `src/agent_arena/constants.py` (termination reason tokens — add `quota_aborted` if missing)
**Files (scope):** `services/referee/_turn_runner.py`, `constants.py` (token only if needed).
**Do:** Add a branch: if the incoming move's `flag == "quota_aborted"`, stop the match and
finalize with `terminated_reason="quota_aborted"` (mirror how disconnect termination is handled).
**Verify:**
```
uv run ruff check src tests
uv run pytest tests/integration/test_debate_faults.py tests/unit/services/referee -q
```
Add a test that feeds a `quota_aborted` move and asserts the match terminates with that reason.
**Commit:** `feat(referee): terminate match on quota_aborted move flag`

---

## B3 — Wire `APIGatekeeper` into the player + abort on exhaustion
**Goal:** The player builds a gatekeeper, injects it into its `LLMClient`, and when the LLM call
raises `GatekeeperError` the player submits a `MOVE_SUBMIT` with `flag="quota_aborted"` instead
of crashing.
**Read first:**
- `src/agent_arena/apps/player_app.py` (`main()` wiring)
- `src/agent_arena/services/player/agent.py` (≈ 87 LLMClient construction; the MOVE_REQUEST handler)
- `src/agent_arena/services/player/brain/llm_brain.py` (where the LLM call happens)
- `src/agent_arena/shared/api_gatekeeper.py` (`GatekeeperError` hierarchy)
**Files (scope):** `apps/player_app.py`, `services/player/agent.py` (and `brain/llm_brain.py` only if the except must live there).
**Do:**
1. Build `APIGatekeeper(**config.llm.gatekeeper.model_dump())` in `player_app.main` and inject it
   into the player's `LLMClient`.
2. In the move-generation path, wrap the LLM call so `GatekeeperError` is caught and the player
   sends `MOVE_SUBMIT(..., flag="quota_aborted")` then stops cleanly.
**Verify:**
```
uv run ruff check src tests
uv run pytest tests/integration/test_player_integration.py tests/unit/services/player -q
```
**Commit:** `feat(player): inject gatekeeper and abort move on quota exhaustion`

---

## B4 — Transcript: gatekeeper section + `quota_aborted` banner
**Goal:** `print_transcript` shows an "API Gatekeeper" section (from `verdict["api_state"]`) and a
loud banner when any turn or the verdict is `quota_aborted`.
**Read first:**
- `src/agent_arena/apps/run_helpers.py` (≈ 46–95: `print_transcript`)
- A real verdict file under `results/` to see the actual `api_state` shape (read, do not modify).
**Files (scope):** `apps/run_helpers.py`.
**Do:** Add a section that renders `verdict.get("api_state")` (RPD used/remaining, breaker state,
tokens) when present, and a prominent banner line when `terminated_reason == "quota_aborted"` or
any turn carries that flag.
**Verify:**
```
uv run ruff check src tests
```
Run `print_transcript` against an existing results file (or a small fixture) and eyeball the new
section. (apps/ is excluded from coverage, so no pytest gate here — lint + manual check.)
**Commit:** `feat(cli): show gatekeeper state and quota_aborted banner in transcript`

---

## B5 — Unit tests for `APIGatekeeper`
**Goal:** Lock the gatekeeper's behavior with a fake clock — this is the biggest untested module.
**Why:** `REMAINING_WORK.md` §1 — `tests/unit/shared/test_api_gatekeeper.py` does not exist.
**Read first:**
- `src/agent_arena/shared/api_gatekeeper.py` (whole file — note it takes a `clock` param for testing)
- `tests/unit/shared/test_watchdog.py` and `test_heartbeat.py` (copy the FakeClock / threading test style used in this repo)
**Files (scope):** new file `tests/unit/shared/test_api_gatekeeper.py` only.
**Do:** Write tests with an injected fake clock covering: token refill, RPD limit + daily reset,
breaker trips after threshold within window, breaker OPEN rejects, OPEN→HALF_OPEN after cooldown,
HALF_OPEN probe success closes / failure re-opens, `acquire` timeout, `gate()` context manager,
`snapshot()` returns JSON-serializable state.
**Verify:**
```
uv run ruff check src tests
uv run pytest tests/unit/shared/test_api_gatekeeper.py -q
uv run pytest -q
```
Coverage for `api_gatekeeper.py` should be high; overall gate stays ≥85%.
**Commit:** `test(gatekeeper): cover refill, RPD, breaker transitions with fake clock`
