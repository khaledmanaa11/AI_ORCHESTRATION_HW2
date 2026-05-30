# Remaining Work — Triplet Audit

Generated 2026-05-30. Each section is the gap report for one PRD/PLAN/TODO triplet
(or orphan PRD), cross-checked against actual code under `src/`, `scripts/`, `results/`.

Sections are filled in by per-module audit agents and assembled by the orchestrator.

---

## 1. api_gatekeeper

### Done
- A1.1–A1.3 File exists, imports present, logger defined — `src/agent_arena/shared/api_gatekeeper.py:1-11`
- A2.1–A2.4 All four exception classes defined with `reason` attr — `api_gatekeeper.py:27-44`
- A3.1 `_BreakerState` enum with CLOSED/OPEN/HALF_OPEN — `api_gatekeeper.py:48-51`
- A4.1–A4.9 Full `APIGatekeeper.__init__` with all 7 config params + `clock`, all state initialized — `api_gatekeeper.py:63-97`
- A5.1–A5.2 `_refill_locked` implemented — `api_gatekeeper.py:106-110`
- A6.1 `_check_rpd_reset_locked` implemented — `api_gatekeeper.py:112-117`
- A7.1–A7.2 `_maybe_transition_open_to_half_open_locked` and `_trip_breaker_locked` implemented — `api_gatekeeper.py:119-134`
- A8.1–A8.12 `acquire` implemented (RPD check, breaker check, token wait, timeout) — `api_gatekeeper.py:136-175`; NOTE: uses `_cond.wait(timeout=remaining)` manual loop, not `cond.wait_for` (A8.8 deviation)
- A9.1–A9.6 `release` fully implemented including HALF_OPEN probe handling and window-based breaker — `api_gatekeeper.py:177-213`
- A10.1–A10.4 `gate` context manager implemented — `api_gatekeeper.py:215-231`
- A11.1–A11.2 `snapshot` implemented, JSON-serializable — `api_gatekeeper.py:233-248`
- B1–B5 `GatekeeperConfig` in `config.py:28-53`, validators present, `LLMConfig.gatekeeper` field present — `config.py:60`
- B4 `setup.json` has `llm.gatekeeper` block — `config/setup.json:22-30`
- C1–C8 `llm_client.py` imports gatekeeper, both backends accept and use it, `gate()` wraps HTTP calls, `GatekeeperError` propagates — `llm_client.py:19,69-101,132-176`
- G1–G2 `shared/__init__.py` re-exports all 5 names — `__init__.py:2-24`

### Missing / Incomplete
- **A8.8 (GK-NFR2 deviation)**: `acquire` uses manual `while True` + `_cond.wait(timeout=remaining)` polling loop (`api_gatekeeper.py:142-165`) instead of `_cond.wait_for(_can_proceed, timeout=...)`.
- **D1–D6 (FR-INT-R1..R4)**: `referee_app.py` never constructs an `APIGatekeeper`, never passes one to `LLMClient`, never catches `GatekeeperError`, never writes `api_state` to verdict, never calls `gatekeeper.snapshot()` on shutdown. Grep `gatekeeper` in `referee_app.py` → 0 hits.
- **E1–E3 (FR-INT-P1..P3)**: `player_app.py` never constructs a gatekeeper. `player/agent.py:87` calls `LLMClient(provider=...)` with no gatekeeper arg (falls through to hidden `get_default_gatekeeper()` singleton). Brain's `MOVE_REQUEST` handler has no `except GatekeeperError` and never submits `flag="quota_aborted"`.
- **D4 / FR-INT-R3**: `_turn_runner.py` has no branch for `flag == "quota_aborted"` on incoming `MOVE_SUBMIT`; grep `quota_aborted` in `services/` → 0 hits.
- **F1–F2 (FR-INT-V1..V2)**: `print_transcript` in `run_helpers.py` has no "API Gatekeeper" section, no `api_state` rendering, no `quota_aborted` banner — `run_helpers.py:46-95`.
- **FR-INT-R4**: verdict JSON never gains `api_state` key; `game_loop.py` and `result.py` have no reference to gatekeeper snapshot.
- **H1–H19, I1–I3**: No test files exist (`tests/unit/shared/test_api_gatekeeper.py`, `tests/integration/test_quota_aborted_verdict.py`, etc. — 0 files found).
- **FR-INT-L7 (C7) violates ADR-GK-001**: `LLMClient.__new__` falls back to `get_default_gatekeeper()` module-level singleton instead of constructing from config when `None`.

### Stale or contradicts code
- **ADR-GK-001** ("no module-level singleton, injected via constructor") contradicted by `api_gatekeeper.py:13-24` (`_DEFAULT_GATEKEEPER` + `get_default_gatekeeper()`) and `llm_client.py:75,141`.
- **PRD FR-CFG4 defaults** (`breaker_threshold=5`, `breaker_window_seconds=30.0`, `breaker_cooldown_seconds=60.0`) contradicted by `setup.json` shipping 15 / 60.0 / 180.0 — 3 of 7 values differ.

### Next concrete steps
1. Wire `referee_app.py`: construct `APIGatekeeper(**config.llm.gatekeeper.model_dump())`, inject into `LLMClient`, catch `GatekeeperError`, write verdict with `terminated_reason="quota_aborted"` + `api_state=gatekeeper.snapshot()`.
2. Wire `player_app.py` + `player/agent.py`: construct gatekeeper at startup, inject into `LLMClient`, add `except GatekeeperError` → submit `MOVE_SUBMIT(flag="quota_aborted")`.
3. Add `quota_aborted` branch in `_turn_runner.py:run_turn` that terminates the match instead of retrying.
4. Add "API Gatekeeper" section + loud banner to `run_helpers.py:print_transcript` when `verdict.get("api_state")` or any turn carries `flag="quota_aborted"`.
5. Create `tests/unit/shared/test_api_gatekeeper.py` with `FakeClock` covering all H1–H19 (GK-AC3/AC4/AC9 currently unverified).

---

## 2. fault_tolerance

### Done
- `ShutdownCoordinator` fully implemented (FR-SC1–SC10) — `src/agent_arena/shared/shutdown.py:9-51`
- `WatchdogThread` fully implemented (FR-WD1–WD11) — `src/agent_arena/shared/watchdog.py:9-56`
- `HeartbeatSender` fully implemented (FR-HB1–HB7) — `src/agent_arena/shared/heartbeat.py:8-39`
- `__init__.py` exports all three classes with `__all__` — `src/agent_arena/shared/__init__.py:10-24`
- Unit tests cover all TODO A7/B7/C7 cases — `tests/unit/shared/test_shutdown.py`, `test_watchdog.py`, `test_heartbeat.py`
- SIGTERM wrapped in `try/except OSError` (A6.4) — `shutdown.py:47-50`
- `_fired` set updated before `_on_timeout` to prevent double-fire, lock released first (FR-WD9) — `watchdog.py:52-54`
- No hardcoded operational timeout in `watchdog.py`/`heartbeat.py` (FR-CFG3)

### Missing / Incomplete
- **FR-INT-R1–R10 (referee integration)**: `RefereeServer` and `DebateGameLoop` import zero FT classes. No `ShutdownCoordinator`, `WatchdogThread`, or `HeartbeatSender` anywhere in `src/agent_arena/services/referee/` or `src/agent_arena/apps/referee_app.py`.
- **FR-INT-P1–P8 (player integration)**: `PlayerClient` and `PlayerAgent` similarly unwired. No `install_signal_handlers`, no `coordinator.wait()`, no watchdog on `"referee"`, no `HeartbeatSender` — `services/player/client.py`, `agent.py`.
- **GAME_OVER/ERROR → `request_shutdown` (FR-INT-P7)**: `PlayerAgent.handle_message` sets `self.game_over = True` on GAME_OVER but never calls `coordinator.request_shutdown` — `agent.py:125-126`.
- **`watchdog.heartbeat` on every recv (FR-INT-R6, FR-INT-P5)**: no call site exists in services or apps.
- **TODO G1–G4 (manual smoke tests)**: explicitly `[ ]` in `TODO_fault_tolerance.md:321-328`.
- **TODO F1–F9 (quality gates)**: all `[ ]` — ruff check, line-count, coverage not run/recorded — `TODO_fault_tolerance.md:293-310`.

### Stale or contradicts code
- TODO items A1–E4 marked `[x]` (done), but the integration requirements they depend on (FR-INT-R1–R10, FR-INT-P1–P8) map only to unchecked G-tasks — gives false impression that referee/player wiring is covered when service code contains none of it.
- `PLAN_fault_tolerance.md §4.1` describes a referee thread map including `HeartbeatSender × 2` + `WatchdogThread`, but `RefereeServer.run_game` (`server.py:102-148`) starts only a bare game thread with no FT wiring.

### Next concrete steps
1. Wire `ShutdownCoordinator` into `RefereeServer.__init__` + `referee_app.main` (call `install_signal_handlers`, register GAME_OVER + socket-close callbacks, block on `coordinator.wait()`) per FR-INT-R1–R10.
2. Wire `WatchdogThread` into `RefereeServer.on_connect` (register each player after connect) and call `watchdog.heartbeat(player_id)` in every `recv` path in `_turn_runner.py`.
3. Wire `ShutdownCoordinator`, `WatchdogThread("referee")`, `HeartbeatSender` into `PlayerClient.start` / `PlayerAgent.run` per FR-INT-P1–P8; replace `self.game_over = True` with `coordinator.request_shutdown("game_over")`.
4. Run `uv run pytest tests/unit/shared/ --cov=src/agent_arena/shared --cov-report=term-missing`, fix any gaps below 85% (TODO F8).

---

## 3. network

### Done
- FR-CH1–CH5, A-tasks: Channel ABC, InMemoryChannel, ConnectionClosedError — `src/agent_arena/shared/transport/channel.py:5-44`
- FR-FR1–FR7, B-tasks: send_frame, recv_frame, FrameTooLargeError, partial-read loop — `src/agent_arena/shared/transport/framing.py:9-36`
- FR-SV1–SV6, C-tasks: TcpServer with accept loop, SO_REUSEADDR, player_count cap, reject-extras, stop() — `src/agent_arena/shared/transport/tcp_server.py:32-95`
- FR-CL1–CL7, D-tasks: TcpClient with exponential backoff, socket timeout, ConnectionFailedError — `src/agent_arena/shared/transport/tcp_client.py:12-63`
- FR-MT1–MT3, E1: MessageType(str, Enum) with all 10 members — `src/agent_arena/services/protocol/message_types.py:4-16`
- FR-EN1–EN4, E2: Envelope frozen dataclass with 7 fields — `src/agent_arena/services/protocol/envelope.py:6-16`
- FR-PL1–PL11, E3: all 10 payload dataclasses frozen — `src/agent_arena/services/protocol/payloads.py:5-65`
- FR-CO1–CO7, F: encode/decode, CodecError, round-trip — `src/agent_arena/services/protocol/codec.py:17-55`
- FR-VA1–VA7, G: validate(), ProtocolVersionError, UnknownMessageTypeError, ValidationError — `src/agent_arena/services/protocol/validation.py:5-30`
- H1/H2: both `__init__.py` wire public names with `__all__` — `transport/__init__.py:1-25`, `protocol/__init__.py:1-43`
- NL-NFR2: no `import socket` anywhere in `services/` (grep → 0)
- NL-G5: NetworkConfig, FramingConfig, GameConfig provide required params — `src/agent_arena/shared/config.py:9-27`
- All 9 test files exist — `tests/unit/shared/transport/`, `tests/unit/services/protocol/`

### Missing / Incomplete
- **NL-AC11**: `PlayerClient` constructs FramedChannel with no max_bytes arg (hardcoded default 10485760) instead of `config.framing.max_frame_size_bytes` — `services/player/client.py:49`.
- **NL-AC7 / FR-CL2 partial break**: `TcpClient.connect()` catches broad `OSError` (not just `ConnectionRefusedError`), masks host-not-found — `tcp_client.py:40`.
- **`validate()` never called by referee or player after decode()** — grep `services/referee/`, `services/player/` for `validate(` → 0 matches. NL-G2 / NL-AC4 version gate not enforced at runtime.
- **`protocol_version` hardcoded as `"1.00"`** in `player/agent.py:53` instead of importing `PROTOCOL_VERSION` constant — vs `src/agent_arena/constants.py:5`.
- **NetworkConfig missing `max_retries` and `backoff_base`** fields; `PlayerClient` falls back to hardcoded 5 and 0.1 — `config.py:9-14`, `client.py:23-24`.

### Stale or contradicts code
- PLAN §2 file structure does NOT list FramedChannel as planned class in `channel.py`, yet it was added — `channel.py:47-89`. This undocumented class duplicates `framing.py` logic and is the actual runtime path.
- TODO H1.1 claims `__all__` exports `TcpChannel`; true in code, but `TcpChannel` is internal and not in the PRD's public API table.

### Next concrete steps
1. Pass `config.framing.max_frame_size_bytes` to FramedChannel in `services/player/client.py:49` (thread config through `PlayerClient.__init__`).
2. Add `validate(env, PROTOCOL_VERSION)` after every decode() in `referee/server.py:77` and `player/agent.py:70`.
3. Replace hardcoded `"1.00"` at `player/agent.py:53` with `from agent_arena.constants import PROTOCOL_VERSION`.
4. Narrow except in `tcp_client.py:40` from `OSError` to `ConnectionRefusedError` (+ optionally `TimeoutError`).
5. Add `max_retries` and `backoff_base` fields to NetworkConfig (NL-AC11, FR-CL7).

---

## 4. player

### Done
- **P0 (shared LLM client)** — `LLMClient` facade present, old `gemini_client.py` absent — `src/agent_arena/shared/llm_client.py:209`
- **P1 (brain contract)** — `PlayerBrain` ABC, `PlayerContext` (frozen), `PlayerDecision` — `services/player/brain/base.py:9,23,31`
- **SeededPlayerBrain conforms (FR-PB4)** — subclasses `PlayerBrain.generate` — `services/player/brain/seeded_brain.py:9`
- **P2 (prompt builder)** — all ablation branches (OFF/ON/alpha), per-vector gating, schema request, gen_params — `services/player/brain/player_prompts.py:50-145`
- **P2 fixture pack (RP2.7)** — `config/fixtures/evidence_pack_test.json` exists
- **P3 (output parser)** — `parse()` with fallback on malformed JSON, targets normalization — `services/player/brain/output_parser.py:18-90`
- **P4 (selector)** — both modes, deterministic tie-break at lowest index — `services/player/brain/selector.py:33-80`
- **P5 (LLMPlayerBrain)** — one call, full FR-PC1 trace, stateless — `services/player/brain/llm_brain.py:37-112`
- **P6 (capture sink)** — BS-5 path, directory creation, `private_capture` gate — `services/player/brain/capture.py:12-39`
- **P7 (agent wiring)** — scratchpad, trace_buffer, GAME_OVER dump, config-driven brain choice — `services/player/agent.py:37-132`
- **Config additions (RP7.5)** — `debate.player.{temperature, top_p, persona_set, selector_weights, best_of_N, ablation}`, `debate.match.{run_id, results_dir}`, `llm.generation_seed` present in `config/setup.json`
- **Unit tests P3-P7** — test files exist — `tests/unit/services/player/brain/`

### Missing / Incomplete
- **BS-4 / RP5.4: generation seed never passed to LLM call** — `build_player_prompt` returns `gen_params` including `seed`, but `llm_brain.py:40` discards them (`prompt_str, _ = build_player_prompt(...)`). `LLMClient.generate_text` has no seed param. `GoogleGenAIClient.generate_text` reads temperature from env only, ignoring config — `shared/llm_client.py:118-121`.
- **PL-AC3 gate guard missing** — no test asserts player modules do not import `google.generativeai` or construct a real client — `tests/unit/services/player/**` → none.
- **PL-AC9 line-count assertion** — no automated per-file line-count check in any test or CI gate.

### Stale or contradicts code
- TODO P3 marked `[x]` done; P4–P7 marked `[x]`. Handoff note at top of `TODO_player.md` says "Start with Module P3" (implying P3 not yet done), but the build-order table shows all ✅. Code confirms all implemented. Handoff note is stale.
- `llm_client.py` temperature/top_p: PRD BS-4 / RP5.4 require these from config; `GoogleGenAIClient.generate_text` reads temperature only from `LLM_TEMPERATURE` env var (`llm_client.py:29-35`), ignoring `gen_params`.

### Next concrete steps
1. Fix `llm_brain.py:40`: capture `gen_params`, pass `temperature`, `top_p`, `seed` to `generate_text` (or new `generate_text_with_params`).
2. Update `LLMClient`/`GoogleGenAIClient.generate_text` to accept optional `temperature`, `top_p`, `seed` kwargs and forward into `GenerateContentConfig`.
3. Add a gate-guard test (PLAN §5) asserting no player brain module imports `google.generativeai` or constructs a real `LLMClient`.

---

## 5. referee

### Done
- `DebateState`/`DebateMove`/`TurnRecord` frozen dataclasses with `to_dict()`/`from_dict()` — `services/game/debate_state.py` (FR-ST2/ST4/ST7)
- `DebateEngine` with `validate_move`, `apply_move`, `is_terminal`, `get_initial_state`, `get_legal_moves` — `services/game/debate_engine.py` (FR-EN1–EN7)
- `RefereeBrain` ABC + `RefereeContext`/`RefereeDecision` + `aggregate_verdict` — `services/referee/brain/base.py:55-122` (FR-RB1–RB7)
- `SimpleRefereeBrain` with concession scan, number-free tell, word-count scores, deterministic tiebreak — `services/referee/brain/simple_brain.py:61-115` (FR-SB1–SB7)
- `LLMRefereeBrain` with 3-arm prompt dispatch + `_verify_grounding` (Arm-3) — `services/referee/brain/llm_brain.py:52-119`
- Turn loop with two-tier legality, retry gate, timeout-as-penalized-skip, `try/finally` GAME_OVER invariant — `services/referee/game_loop.py:87-134`, `_turn_runner.py:89-155` (FR-FT1, FR-FT7)
- Disconnect → forced verdict tagged `terminated_reason` — `game_loop.py:89-97` (FR-FT4)
- `MALFORMED_MESSAGE` content drop vs stream-broken escalation — `_turn_runner.py:109-117` (FR-FT5)
- Error-code and reason tokens in `constants.py:29-44` (RG2.1/RG2.2)
- `PROTOCOL_VERSION = "1.00"` unchanged — `constants.py:5`
- Sweep runner with 3 variants × K mirror pairs (ON/OFF) — `apps/sweep_runner.py:248-261`
- Stream A (trajectory) + Stream C (metadata) written — `sweep_runner.py:138-165` (FR-EX4 partial)
- Evidence pack — `data/evidence_pack_primary.json` (RJ1.1)

### Missing / Incomplete
- **Heartbeat/watchdog not wired into referee turn loop** — `WatchdogThread`/`HeartbeatSender` exist in `shared/` but never imported in `services/referee/`. FR-FT2/FR-FT3 (RE5.3/RE5.4) deferred per TODO; still absent post-Module-H.
- **Stream B (player private-capture) not aggregated by sweep runner** — `sweep_runner.py:write_streams` writes only Stream A + C; capture.py writes per-player files but sweep runner never collects into `stream_b_private_capture.jsonl` (FR-EX4/RJ3.1).
- **Mirror-pair `first_speaker` flip not implemented** — `sweep_runner.py:248-251` runs `(variant, seed, True, False)` + `(variant, seed, False, True)` but never flips `first_speaker`. PRD FR-EX2/RJ2.2 requires the paired matches swap `first_speaker`.
- **Per-vector teardown mode absent** — no one-at-a-time vector loop in `sweep_runner.py`. TODO `RJ2.3` marked `[x]` but implementation missing.
- **`result.py` duplicates `TERMINATED_*` constants** — `result.py:11-12` re-declares tokens that already live in `constants.py:43-44`.
- **RK.5 (AC9 CI guard) not implemented** — TODO `RK.5` still `[ ]`; no CI check asserts `git diff services/protocol/` is empty.
- **Analysis notebook hypothesis reporting H1–H5 (RJ4.3/FR-EX7) + READ partial-correlation cell (RJ4.2/FR-EX5)** unverified without running.

### Stale or contradicts code
- TODO Module I marked `✅ DONE` but `LLMRefereeBrain._verify_grounding` uses naive `doc_id in text` substring check (`llm_brain.py:96-102`) — checks whether pack key appears literally in utterance, not citation verification against evidence content. Contradicts FR-JU7.
- TODO Module J (`RJ2.1–RJ2.2`) marked `[x]` but mirror-pair `first_speaker` flip absent.
- `result.py` owns `TERMINATED_DISCONNECT`/`TERMINATED_ABORTED`, but PLAN §2 says they live in `constants.py` — duplicate source of truth.

### Next concrete steps
1. Wire `WatchdogThread` + `HeartbeatSender` into `services/referee/server.py` (or `game_loop.py`) so FR-FT2/FT3 are enforced at runtime.
2. Implement `first_speaker` flip in `sweep_runner.py:worker` — flip `cfg.debate.format.first_speaker` for the second match in each mirror pair.
3. Add Stream B aggregation to `sweep_runner.py:write_streams` — collect per-player private-capture JSONL keyed on `(match_id, seed, turn_number)`.
4. Delete `result.py:11-12` duplicates and import from `constants`.
5. Add CI step asserting `git diff --name-only HEAD -- src/agent_arena/services/protocol/` is empty AND `PROTOCOL_VERSION == "1.00"` (RK.5).

---

## 6. submission

### Done
- S1 (Run 4 gatekeeper live validation), S1.1–S1.5 — `results/c4229c3e_trajectory.jsonl`, `docs/devlog/2026-05-28-run4-gatekeeper-live.md`, `docs/CURRENT_STATE.md:86-97`
- S2 (`[referee tell]` side-label fix) S2.1–S2.4 — `docs/devlog/2026-05-28-referee-side-swap-fix.md`; `TODO_submission.md:57-61` all `[x]`
- Sweep idempotency guard (FR-SW-6) — `apps/sweep_runner.py:184-188` raises `SystemExit` when dir non-empty
- `GatekeeperExhaustedError` clean-halt (FR-SW-4) — `apps/sweep_concurrency.py:32-38`
- `summary.json` schema (FR-SW-5 fields) — `sweep_003/summary.json` has all 10 required fields
- `docs/PROMPTS.md` exists (S5.1) — `docs/PROMPTS.md:1`
- `results/sweep_003/` with 255 trajectory files + `summary.json`

### Missing / Incomplete
- **S3 not completed against `sweep_001/`** (FR-SW-3, S-G2, PLAN §6 item 4): `sweep_001/summary.json` shows `completed=12, total_matches=12` — a 12-match test, not the required ≥ 250. The 255-file run is in `sweep_003/`. Notebook hardcodes `../results/stream_a_trajectory.jsonl` (cell 3), not `sweep_001/`.
- **S4 notebook (FR-NB-2/3/5)**: paths not parameterized at top; no `summary.json` read; no saved outputs; missing forfeit/quota-abort figure and best_of_N comparison. Cells contain mock values (`win_rates = {"naive": 0.72, ...}`), zero saved outputs.
- **S4.4 `notebooks/analysis.html` missing** — `ls notebooks/` returns only `analysis.ipynb`.
- **S5 PROMPTS.md only 1 entry; requires ≥ 3 (S-AC6, FR-PL-2)** — Entry 001 only; no referee-judge, PRO-brain, CON-brain, sweep-instruction entries.
- **S6 README missing Troubleshooting + Examples/screenshots sections (FR-RM-4, FR-RM-5)** — grep "Troubleshoot/503/429/GatekeeperOpen" → 0; line 86 still says "Screenshots … will be added".
- **S6 README missing `llm.gatekeeper` config block (FR-RM-3)** — `README.md:107` stops at `llm.model_name`.
- **S7 architecture diagram absent (S-AC8, FR-AD-1/2/3)** — `ls assets/` empty.
- **S8 final gate devlog `docs/devlog/2026-05-28-submission-gate.md` does not exist**.
- **S8.5 `CURRENT_STATE.md` not rewritten as submission snapshot (FR-GT-3, S-AC12)** — still in experiment-narrative form, not one-line `Submission-ready snapshot taken at <commit> on <date>`.

### Stale or contradicts code
- TODO S3 shows `[ ]` (not started) but `results/sweep_003/` has 255 trajectories with `completed=8` (242 forfeited, breaker OPEN) — the sweep ran but into a dead breaker; TODO never updated.
- PRD FR-SW-3 mandates output in `results/sweep_001/`; actual 255-file run is in `sweep_003/`; `sweep_001/` has only 12 offline matches.
- `docs/PROMPTS.md` Entry 001 records design decision to delete `PRD_gatekeeper.md` and use Anthropic SDK (no gatekeeper) — contradicts current codebase which uses full Gemini-API gatekeeper. Log never updated.

### Next concrete steps
1. Rename or re-run the canonical sweep into `results/sweep_001/` (or update PRD/PLAN/TODO references to `sweep_003/` and document discrepancy in a devlog).
2. Rewrite `notebooks/analysis.ipynb`: add parameterized `SWEEP_DIR` at cell 0, load `summary.json`, replace mock values with real computations, add forfeit/quota-abort + best_of_N cells, run top-to-bottom, export `analysis.html`.
3. Add ≥ 2 more entries to `docs/PROMPTS.md` (referee judge, PRO/CON player brains) matching FR-PL-3.
4. Add README Troubleshooting (429, 503, `GatekeeperOpenError`, `GatekeeperExhaustedError`, port-in-use) + real Examples/screenshots section.
5. Create `assets/architecture.png` (or `.mmd` + exported PNG); reference from `README.md` and `PLAN.md §1`.
6. Run final gate (`uv run pytest -q && uv run ruff check src tests`), append output to `docs/devlog/2026-05-28-submission-gate.md`, then rewrite `CURRENT_STATE.md` to one-screen submission snapshot.

---

## 7. top-level (PRD.md / PLAN.md / TODO.md)

### Done
- **M1 Foundation** — `shared/version.py` VERSION="1.00": `shared/version.py:1`; `shared/config.py` loads/validates: `shared/config.py:12-18`; `constants.py` exists
- **M2 Transport** — Channel, Framing, TCPServer, TCPClient present; TCPServer rejects beyond `player_count`: `transport/tcp_server.py:68`
- **M3 Protocol** — All five protocol files present: `services/protocol/{message_types,envelope,payloads,codec,validation}.py`
- **M4 Referee partial** — game_loop + `_turn_runner`; result.py; referee brain base + simple + llm; server wired (`services/referee/server.py:30-102`); matchmaking (debate-specific `setup_match`): `services/referee/matchmaking.py:94`
- **M5 Player** — PlayerBrain base, LLMPlayerBrain, player agent + client all present
- **M7 LLM partial** — LLMClient (Google Gemini, not Anthropic) with retry/backoff: `shared/llm_client.py:66-237`; LLMRefereeBrain + LLMPlayerBrain implemented
- **Console scripts** — `uv run referee` / `uv run player` registered: `pyproject.toml:14-15` (apps call services directly, not through ArenaSDK)
- **Coverage gate** — `fail_under = 85` in `pyproject.toml:48`; last run reported 94.19% per CURRENT_STATE.md
- **T0.4 per-mechanism PRDs** — `PRD_protocol.md`, `PRD_matchmaking.md`, `PRD_game_engine.md` exist; `PRD_referee_brain.md` **absent**
- **T0.5 PROMPTS.md** exists

### Missing / Incomplete
- **T0.4 `PRD_referee_brain.md` missing** — Glob confirms 0 files
- **T6.1 ArenaSDK stub only** — `sdk/sdk.py` is `class ArenaSDK: pass` (3 lines); `start_referee()` / `start_player()` not implemented; apps bypass SDK entirely
- **T5.2 `random_brain.py` missing** — no file anywhere under `src/`; TODO T5.2 still open; `SeededPlayerBrain` exists as substitute but is debate-specific, not the generic phase-1 placeholder
- **T6.3 integration test missing** — no file covers real referee + 2 players to GAME_OVER via the standard protocol; existing tests are unit-level
- **LLMCallerMixin in shared** — PLAN §5.10 / T7.1 require `shared/llm_caller.py` with the mixin as single SDK import point; instead defined locally in `services/referee/brain/llm_brain.py:45`; `LLMPlayerBrain` does not inherit it

### Stale or contradicts code
- **PRD/PLAN specify Anthropic SDK** — PRD §3.4, FR-L1–L3 and PLAN §8 mandate `anthropic` Python SDK + `ANTHROPIC_API_KEY`; actual implementation uses `google.genai` SDK + `GOOGLE_API_KEY` (`shared/llm_client.py:14,71`); no Anthropic dependency anywhere.
- **PLAN §3 / T6.1 "all logic flows through ArenaSDK"** — apps call `RefereeServer` and player services directly; `ArenaSDK` is a 3-line `pass` stub; architectural rule violated.
- **TODO T4.2 `trivial_game.py` "skipped"** — TODO says skipped in favour of `DebateEngine`; `PLAN.md` still lists `trivial_game.py` as phase-1 placeholder in §4 skeleton.
- **TODO T4.4 matchmaking marked "⏳ next to implement"** — actual `matchmaking.py` is fully implemented; TODO status stale.

### Next concrete steps
1. Mark `docs/TODO.md` T4.4 as `[x]` and update the note — `matchmaking.py` is complete.
2. Write `docs/PRD_referee_brain.md` (T0.4 final missing per-mechanism PRD).
3. Implement `sdk/sdk.py` `start_referee()` / `start_player()` and wire `referee_app.py` / `player_app.py` through `ArenaSDK` (T6.1).
4. Move `LLMCallerMixin` to `shared/llm_caller.py` and have both `LLMRefereeBrain` and `LLMPlayerBrain` inherit (T7.1).
5. Add one integration test: referee + 2 players over localhost to `GAME_OVER` (T6.3 / AC3).
6. Resolve the **Anthropic-vs-Gemini** drift — either rewrite docs to reflect Gemini reality or migrate code to Anthropic SDK (note: 2026-05-28 memory says Gemini paid tier was chosen for this homework → docs should be updated).

---

## 8. game_engine (orphan PRD — no PLAN/TODO)

### Done
- `GameEngine` ABC with `get_initial_state`, `validate_move`, `apply_move`, `get_legal_moves`, `is_terminal` — `services/game/engine_base.py:8-34`
- `DebateEngine` implements all five — `services/game/debate_engine.py:44,55,69,90,136`
- `get_initial_state()` returns start state — `debate_engine.py:44-53`
- `validate_move` returns `(bool, reason_token|None)` — `debate_engine.py:55-67`
- `apply_move` never mutates input (returns fresh frozen `DebateState`) — `debate_engine.py:90-134`
- `get_legal_moves` returns constraint descriptor per turn — `debate_engine.py:69-88`
- State JSON-serializable via `DebateState.to_dict()` / `from_dict()` — `services/game/debate_state.py:107-135`
- Determinism declared: "pure deterministic, no LLM/network/disk" — `debate_engine.py:1,9`
- Referee invokes all five methods — `services/referee/game_loop.py:80,101`, `_turn_runner.py:85,105,120,126,139,147`
- `GAME_OVER` message type defined — `services/protocol/message_types.py:14`

### Missing / Incomplete
- **No `docs/PLAN_game_engine.md` exists** — process gap, blocks tracking
- **No `docs/TODO_game_engine.md` exists** — process gap, blocks tracking
- PRD §2 specifies `validate_move(state, move, role)`; actual is `validate_move(state, move)` — no role enforcement in engine; out-of-turn rejection handled externally by `_turn_runner.py` routing
- PRD §2 specifies `check_terminal(state)` returning `(is_terminal: bool, winner: role_or_none)`; implemented as `is_terminal(state) -> bool`; winner determination absent from engine interface, delegated to `referee/brain/`
- No deterministic replay mechanism (no replay-from-transcript test path or documented contract)
- `apply_move` PRD spec requires `role` parameter; actual signature uses `**kwargs` with no role

### Stale or contradicts code
- PRD §2 method name `check_terminal` does not match implemented `is_terminal` — `engine_base.py:32`
- PRD §2 `validate_move` / `apply_move` signatures include `role` argument; code omits it — role awareness pushed to `_turn_runner.py:83` outside engine contract

### Next concrete steps
1. Draft `docs/PLAN_game_engine.md` from the PRD, mapping each I/O requirement to its implementing file and open gaps.
2. Create `docs/TODO_game_engine.md` with at minimum: add `role` param to `validate_move`/`apply_move` in `engine_base.py`; rename or alias `is_terminal` to `check_terminal` returning `(bool, winner_or_none)`.
3. Update `engine_base.py:16` to add `role` parameter to `validate_move` and enforce out-of-turn rejection inside the engine.

---

## 9. matchmaking (orphan PRD — no PLAN/TODO)

### Done
- REGISTER accepted as first message only — `services/referee/server.py:78-81`
- `agent_id` extracted from `env.sender` on REGISTER — `server.py:82-90`
- `protocol_version` field present in envelope — `services/protocol/envelope.py:10`, `codec.py:7,23,48`
- Protocol version validation logic implemented (`validate()`) — `services/protocol/validation.py:17-22`
- `REGISTER_ACK` sent with `match_id` after both players connect — `server.py:123`
- `ROLE_ASSIGN` sent with role + `game_config` — `server.py:124-131`
- Exactly 2 players enforced: game starts only when `len(registered_players) == player_count` — `server.py:91`
- Third+ connections rejected at TCP level (socket closed, no error message) — `transport/tcp_server.py:83-90`
- Role assignment `PRO`/`CON`, seeded and deterministic — `services/referee/matchmaking.py:58-68`
- `match_id` generated via `uuid4()` in `run_game` — `server.py:104`
- "plumb real match_id" commit landed: `self.match_id` exposed, `write_streams` receives explicit `match_id` — commit `1fefb40`, `apps/sweep_runner.py:116,239,245`
- `GAME_START` sent at start of game loop — `services/referee/game_loop.py:84`

### Missing / Incomplete
- **No `PLAN_matchmaking.md` exists** — process gap, blocks tracking
- **No `TODO_matchmaking.md` exists** — process gap, blocks tracking
- **Protocol version check never invoked during REGISTER** — `validate()` exists at `validation.py:17`, but `server.py:70-96` never calls it. A mismatched-version client is silently accepted.
- **Third-connection rejection sends no `ERROR` message** as PRD §3 specifies — bare socket close only (`tcp_server.py:89-90`)
- **Pre-registration disconnect edge case (PRD §5)**: if Player A disconnects before Player B connects, `registered_players` is never cleaned up; server waits forever. No timeout or removal logic in `server.py`.

### Stale or contradicts code
- PRD §2 says `ROLE_ASSIGN` assigns `PLAYER_1`/`PLAYER_2` or `X`/`O`; actual roles are `PRO`/`CON` — `services/referee/matchmaking.py:13`
- PRD §3 says third client must receive an `ERROR` message; code only closes the socket silently — `transport/tcp_server.py:83-90`

### Next concrete steps
1. Call `validate(env, PROTOCOL_VERSION)` inside `server.py:on_connect` after `decode()` (line 77); send `ERROR` and close on `ProtocolVersionError`.
2. Send an `ERROR` message before closing extra connections in `tcp_server.py:_reject_extras` (line 88-90).
3. Add pre-registration disconnect timeout in `server.py:on_connect`: if a registered player's channel goes dead before game starts, remove from `registered_players` and log.
4. Update PRD §2 to replace `PLAYER_1`/`PLAYER_2`/`X`/`O` with `PRO`/`CON`.
5. Create `docs/PLAN_matchmaking.md` and `docs/TODO_matchmaking.md`.

---

## 10. protocol (orphan PRD — no PLAN/TODO)

### Done
- Envelope schema (all 7 required fields) — `services/protocol/envelope.py:7-16`
- JSON/UTF-8 serialization — `services/protocol/codec.py:31` (`json.dumps(obj).encode("utf-8")`)
- 4-byte big-endian length-prefix framing — `shared/transport/framing.py:5-6` (`_HEADER_FORMAT = ">I"`)
- 10 MB max frame size defined — `constants.py:27` (`DEFAULT_MAX_FRAME_SIZE = 10*1024*1024`) and `shared/config.py:26`
- Oversized frame rejection — `transport/framing.py:30-32`, `transport/channel.py:69-72`
- Partial-read / buffering handled — `transport/framing.py:18-25` (`_fill` loop)
- `protocol_version` fixed at `"1.00"` — `services/player/agent.py:53`
- `ProtocolVersionError` class — `services/protocol/validation.py:5-7`
- `validate()` checks version, type, match_id, seq — `services/protocol/validation.py:17-31`
- All message types defined including REGISTER, REGISTER_ACK, ROLE_ASSIGN, ERROR, HEARTBEAT — `services/protocol/message_types.py:7-16`
- All payload dataclasses — `services/protocol/payloads.py:5-65`
- REGISTER → REGISTER_ACK → ROLE_ASSIGN happy path — `services/referee/server.py:78,123,128`
- Connect timeout configurable — `transport/tcp_client.py:23,37`
- Read timeout at registration — `services/referee/server.py:73`

### Missing / Incomplete
- **No `docs/PLAN_protocol.md` exists** — process gap, blocks tracking
- **No `docs/TODO_protocol.md` exists** — process gap, blocks tracking
- **`validate()` never called on inbound envelopes in referee** — grep `services/referee/**/*.py` for `validate(env` → 0 matches. Version mismatch on REGISTER goes undetected; no typed ERROR sent.
- **SDK stub empty** — `sdk/sdk.py:1-3` (`pass`); PRD §1 states protocol decouples agents from transport, but SDK exposes nothing.
- **No `read_timeout` / `write_timeout` enforcement after registration** — only `server.py:73` uses `recv_timed`; game-loop sends/recvs on channels with no socket timeout (`tcp_client.py:51`: `sock.settimeout(None)`)
- **`ErrorPayload.code` is untyped `str`** — no enum of error codes; PRD §5 implies versioned codes (`VERSION_MISMATCH`), only `"MALFORMED_MESSAGE"` is used in `server.py:66`

### Stale or contradicts code
- PRD §5: "referee sends a typed error and closes the connection" on version mismatch — reality: referee never checks `protocol_version` on inbound REGISTER (`server.py:78-95`); only message type is checked, no version validation.

### Next concrete steps
1. Call `validate(env, PROTOCOL_VERSION)` in `server.py:on_connect` after `decode(raw)`; send `{"code": "VERSION_MISMATCH", ...}` ERROR before closing on `ProtocolVersionError`.
2. Create `docs/PLAN_protocol.md` and `docs/TODO_protocol.md`.
3. Add an `ErrorCode` enum to `services/protocol/message_types.py` and use it in `_send_error`.
4. Implement `ArenaSDK` in `sdk/sdk.py` to expose at minimum `send`/`recv` over the protocol.
5. Enforce read/write socket timeouts post-handshake in `game_loop.py` or `channel.py`.
