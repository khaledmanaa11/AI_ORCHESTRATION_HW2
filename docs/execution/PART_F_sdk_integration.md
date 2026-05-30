# PART F — SDK & integration

The PRD/PLAN say everything flows through `ArenaSDK`, but it's a 3-line `pass` stub and the apps
bypass it. Reference: `REMAINING_WORK.md` §7, §10. F2 depends on F1.

---

## F1 — Implement `ArenaSDK`
**Goal:** `ArenaSDK` becomes the single entry point exposing `start_referee(...)` and
`start_player(...)` that the apps call.
**Read first:**
- `src/agent_arena/sdk/sdk.py` (currently `class ArenaSDK: pass`)
- `src/agent_arena/apps/referee_app.py` and `player_app.py` (the wiring they do today — that logic is what moves into the SDK)
- `docs/PLAN.md §3` and `docs/TODO.md T6.1` (the SDK contract)
**Files (scope):** `sdk/sdk.py`.
**Do:** Implement `ArenaSDK` with `start_referee(config, ...)` and `start_player(config, ...)`
that construct and run the referee server / player client exactly as the apps currently do
(config load, gatekeeper, fault-tolerance, transport). Keep it a thin orchestration seam — no new
behavior, just the existing wiring moved behind two methods.
**Verify:**
```
uv run ruff check src tests
uv run pytest -q
```
Add a unit test that `ArenaSDK` exposes `start_referee` and `start_player` (callable, right signature).
**Commit:** `feat(sdk): implement ArenaSDK.start_referee / start_player`

---

## F2 — Route the apps through `ArenaSDK`
**Goal:** `referee_app.main` and `player_app.main` become thin wrappers that just call the SDK.
**Read first:** `apps/referee_app.py`, `apps/player_app.py`, `sdk/sdk.py` (after F1).
**Files (scope):** `apps/referee_app.py`, `apps/player_app.py`.
**Do:** Replace the inline wiring in each `main()` with `ArenaSDK(...).start_referee(...)` /
`start_player(...)`. Behavior must be identical; the console scripts `uv run referee` /
`uv run player` must still work.
**Verify:**
```
uv run ruff check src tests
uv run pytest -q
uv run referee --help   # or launch briefly; must not error on startup
```
**Commit:** `refactor(apps): route referee/player entry points through ArenaSDK`

---

## F3 — Centralize `LLMCallerMixin`
**Goal:** Move `LLMCallerMixin` into `shared/llm_caller.py` so both the referee brain and player
brain inherit it from one place (PLAN §5.10 / T7.1).
**Read first:**
- `src/agent_arena/services/referee/brain/llm_brain.py` (≈ 45 — mixin defined locally here)
- `src/agent_arena/services/player/brain/llm_brain.py` (does NOT inherit it today)
**Files (scope):** new `shared/llm_caller.py`; edit both `brain/llm_brain.py` files; `shared/__init__.py` export.
**Do:** Create `shared/llm_caller.py` containing `LLMCallerMixin` (moved verbatim from the referee
brain). Have both `LLMRefereeBrain` and `LLMPlayerBrain` import and inherit it. Remove the local
copy. Export from `shared/__init__.py`.
**Verify:**
```
uv run ruff check src tests
uv run pytest tests/unit/services -q
uv run pytest -q
```
**Commit:** `refactor(llm): centralize LLMCallerMixin in shared/llm_caller.py`

---

## F4 — Real-TCP integration test (referee + 2 players → GAME_OVER)
**Goal:** One test that boots a real referee on localhost, connects two real player clients over
TCP, and asserts the match reaches `GAME_OVER` with a verdict.
**Read first:**
- `tests/integration/test_debate_loop.py` and `tests/integration/test_player_integration.py`
  — **check whether either already does this over real sockets.** If one does, this step is just
  verifying/extending it; if they use in-memory channels, add the real-socket variant.
- `tests/conftest.py` (fixtures available)
- player/referee brains: use the **seeded/offline** brains (no live LLM) so the test is hermetic.
**Files (scope):** `tests/integration/` (extend an existing file or add `test_localhost_match.py`).
**Do:** If no real-TCP 2-player→GAME_OVER test exists, add one using ephemeral ports and seeded
brains; assert a verdict with a winner/terminated_reason is produced. If it already exists, mark
the step done with a note pointing to the test.
**Verify:**
```
uv run ruff check src tests
uv run pytest tests/integration -q
```
**Commit:** `test(integration): real-TCP referee + 2 players to GAME_OVER`

---

## F5 — Socket timeouts after the handshake
**Goal:** After registration, the game-loop sockets must have read/write timeouts so a stalled
peer can't hang the match forever (today `sock.settimeout(None)` after connect).
**Read first:**
- `src/agent_arena/shared/transport/tcp_client.py` (≈ 51 — `sock.settimeout(None)`)
- `src/agent_arena/services/referee/game_loop.py` and `_turn_runner.py` (the recv/send sites)
- the timeout values already in `config.py` (reuse them; don't invent new magic numbers)
**Files (scope):** `shared/transport/` and/or `services/referee/game_loop.py` (wherever the timeout is set).
**Do:** Apply a configured read/write timeout to the channel sockets used during the game loop,
and make sure a timeout surfaces as a handled event (forfeit / terminated_reason), not an
unhandled exception. Coordinate with the watchdog from Part C — don't double-kill.
**Verify:**
```
uv run ruff check src tests
uv run pytest tests/integration/test_debate_faults.py -q
uv run pytest -q
```
**Commit:** `fix(transport): apply read/write timeouts to game-loop sockets`
