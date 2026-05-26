# Task Tracking (TODO) — Agent Arena

| Field | Value |
|-------|-------|
| Project | `agent-arena` |
| Version | 1.00 |
| Date | 2026-05-24 |

> Follows guidelines §2.2. Status: `[ ]` not started · `[~]` in progress · `[x]` authored (pending formal approval).
> Each task includes a **Definition of Done (DoD)**. Companion: [PRD.md](PRD.md) · [PLAN.md](PLAN.md).

---

## Phase 0 — Documentation & Scaffolding (Milestone M0)
- [x] **T0.1** Write `docs/PRD.md`. — *DoD:* document authored; approved before development starts.
- [x] **T0.2** Write `docs/PLAN.md`. — *DoD:* architecture + skeleton agreed.
- [x] **T0.3** Write `docs/TODO.md`. — *DoD:* this file.
- [ ] **T0.4** Write per-mechanism PRDs: `PRD_protocol.md`, `PRD_matchmaking.md`,
      `PRD_game_engine.md`, `PRD_referee_brain.md`. — *DoD:* each covers purpose, I/O,
      constraints, alternatives, and edge-case test scenarios.
- [ ] **T0.5** Create `docs/PROMPTS.md` (prompt-engineering log, §8.3). — *DoD:* file exists;
      header and first entry added; updated after every significant LLM interaction.
- [ ] **T0.6** Initialize repo skeleton: `pyproject.toml` (deps, ruff config, coverage config
      with `apps/` omit, console scripts `referee`/`player`), `uv.lock` via `uv sync`,
      `.gitignore` (must include `.env`, `*.key`, `*.pem`, `credentials.json`,
      `__pycache__`, `.venv`, `results/*.log`), `.env-example`, `README.md` (stub),
      all empty package directories + `__init__.py` files, `data/`, `results/`,
      `notebooks/`, `assets/`. — *DoD:* `uv sync` succeeds; `ruff check` clean on empty
      tree; directory structure matches PLAN §4 exactly.

## Phase 1 — Foundation (Milestone M1)
- [x] **T1.1** `shared/version.py` — `VERSION = "1.00"`, exported as `__version__`. —
      *DoD:* importable; tested.
- [x] **T1.2** `config/setup.json` — `host`, `port`, `player_count`, `move_timeout`,
      `lobby_timeout`, `heartbeat_interval`, `framing_scheme`, `llm_model_name`,
      `"version": "1.00"`. `config/logging_config.json`. — *DoD:* no operational value
      lives in source; file is version-stamped.
- [x] **T1.3** `shared/config.py` — load + validate config files; reject mismatched
      `version`. — *DoD:* tested; version mismatch raises a typed error.
- [x] **T1.4** `shared/logging_setup.py` — structured logging from `logging_config.json`;
      outputs to `results/`. — *DoD:* tested; log level changeable without code edit.
- [x] **T1.5** `constants.py` — immutable constants and config-key names. — *DoD:* no
      magic strings anywhere else in the codebase.

## Phase 2 — Transport (Milestone M2)
- [x] **T2.1** `shared/transport/channel.py` — `Channel` abstract interface
      (send/receive methods; timeout parameter). — *DoD:* interface documented; mockable
      in tests without a real socket.
- [x] **T2.2** `shared/transport/framing.py` — length-prefix framing (4-byte big-endian
      header). — *DoD:* handles partial reads, oversized frames, and empty streams; tested.
- [x] **T2.3** `shared/transport/tcp_server.py` — bind/listen/accept; spawns one thread
      per connection; hands messages to a thread-safe Queue. — *DoD:* accepts N clients;
      rejects beyond `player_count`; tested with mock clients.
- [x] **T2.4** `shared/transport/tcp_client.py` — connect with exponential backoff; send/
      recv via `Channel`. — *DoD:* retry policy from config; tested.
- [x] **T2.5** Unit tests: two in-memory channels exchange a framed message; framing edge
      cases pass. — *DoD:* coverage on all framing paths ≥ 85 %.

## Phase 3 — Protocol (Milestone M3)
- [x] **T3.1** `protocol/message_types.py` — `MessageType` enum covering all lifecycle
      types (PLAN §6.2). — *DoD:* no string literals used elsewhere for message types.
- [x] **T3.2** `protocol/envelope.py` — envelope dataclass (`protocol_version`, `type`,
      `match_id` nullable, `sender`, `seq`, `timestamp`, `payload`). — *DoD:* `match_id`
      is explicitly nullable; tested.
- [x] **T3.3** `protocol/payloads.py` — per-type payload schemas (one class per message
      type). Split from envelope to respect the ≤ 150-line rule. — *DoD:* all types from
      §6.2 represented.
- [x] **T3.4** `protocol/codec.py` — encode envelope → bytes; decode bytes → envelope. —
      *DoD:* round-trip tested; malformed input raises typed error.
- [x] **T3.5** `protocol/validation.py` — check `protocol_version`; check type is known;
      check payload schema. — *DoD:* incompatible version and unknown type each produce
      typed rejections.

## Phase 4 — Referee (Milestone M4)
- [x] **T4.1** `services/game/engine_base.py` — `GameEngine` abstract interface
      (PLAN §5.7). — *DoD:* interface documented; mockable. ✅ commit 557cfe5
- [ ] **T4.2** `services/game/trivial_game.py` — placeholder `GameEngine`. — *DoD:*
      produces a terminal state within ≤ 10 turns; exercised by integration tests.
      **NOTE:** skipped — `DebateEngine` serves as the concrete engine directly.
- [x] **T4.3** `services/game/debate_state.py` — debate game state model; immutable
      frozen dataclasses (`TurnRecord`, `DebateMove`, `DebateState`). — *DoD:* tested;
      round-trips + public-only invariant pass. ✅ commit a4b4aaf
- [ ] **T4.4** `services/referee/matchmaking.py` — accept exactly `player_count` players;
      reject 3rd; handle `lobby_timeout`; assign unique roles; send `REGISTER_ACK` (with
      `match_id`) then `ROLE_ASSIGN` as separate messages. — *DoD:* AC1, AC2; lobby
      timeout tested. ⏳ **Module F — next to implement**
- [x] **T4.5** `services/referee/game_loop.py` + `_turn_runner.py` — turn orchestration;
      two-tier move validation; retry gate; timeout/disconnect fault policy; broadcasts
      `STATE_UPDATE`. — *DoD:* all fault paths tested. ✅ commit bc00e69
- [x] **T4.6** `services/referee/result.py` — `GAME_OVER` broadcast + trajectory dump. —
      *DoD:* tested for complete, disconnect, and aborted paths. ✅ commit bc00e69
- [x] **T4.7** `services/referee/brain/base.py` — `RefereeBrain` abstract interface
      (`RefereeContext` in, `RefereeDecision` out). — *DoD:* interface documented; mockable.
      ✅ commit 4703095
- [x] **T4.8** `services/referee/brain/simple_brain.py` — deterministic word-count brain;
      concession scan; no external calls. — *DoD:* tested; deterministic. ✅ commit 12f5004
- [ ] **T4.9** `services/referee/server.py` — wires together matchmaking, game loop,
      result, and teardown. — *DoD:* runs full loop against stub brains and channels.
      ⏳ **Module H (integration gate)**

## Phase 5 — Player (Milestone M5)
- [ ] **T5.1** `services/player/brain/base.py` — `PlayerBrain` abstract interface
      (state + legal-move hints in, move out). — *DoD:* interface documented; mockable.
- [ ] **T5.2** `services/player/brain/random_brain.py` — returns a random legal move. —
      *DoD:* tested; never returns an illegal move.
- [ ] **T5.3** `services/player/agent.py` — message-handling loop; routes all lifecycle
      messages correctly. — *DoD:* tested with mock channel + mock brain.
- [ ] **T5.4** `services/player/client.py` — connection lifecycle; completes handshake;
      delegates to `agent`. — *DoD:* tested with mock server.

## Phase 6 — SDK, Entry Points & Integration (Milestone M6)
- [ ] **T6.1** `sdk/sdk.py` — `ArenaSDK` with `start_referee(config)` and
      `start_player(config)`. — *DoD:* all logic reachable via SDK; entry points contain
      no logic.
- [ ] **T6.2** `apps/referee_app.py` and `apps/player_app.py` — thin console scripts;
      parse CLI args; call `ArenaSDK`. — *DoD:* `uv run referee` and `uv run player`
      launch correctly.
- [ ] **T6.3** Integration test: real referee + 2 players over localhost, trivial game runs
      to `GAME_OVER`. — *DoD:* AC3 reproducible; passes in CI.

## Phase 7 — Pro Phase: LLM Brains (Milestone M7)
- [ ] **T7.1** `shared/llm_caller.py` — `LLMCallerMixin`; wraps Anthropic SDK call;
      reads `ANTHROPIC_API_KEY` from env; model name from config. — *DoD:* SDK import in
      one place only; mocked in tests (no real API calls in unit tests).
- [ ] **T7.2** `services/referee/brain/llm_brain.py` — `LLMRefereeBrain(LLMCallerMixin,
      RefereeBrain)`; builds referee-specific prompts; calls `LLMCallerMixin`. — *DoD:*
      AC9 (no transport change); tested with mocked `LLMCallerMixin`.
- [ ] **T7.3** `services/player/brain/llm_brain.py` — `LLMPlayerBrain(LLMCallerMixin,
      PlayerBrain)`; builds player-specific prompts. — *DoD:* same as T7.2.
- [ ] **T7.4** End-to-end LLM test: all three agents run with LLM brains; full match
      completes; no transport-layer changes from Phase 6. — *DoD:* AC9 confirmed.

## Cross-cutting (every phase)
- [ ] **TC.1** TDD: write tests before/with each module; maintain global coverage ≥ 85 %. —
      *DoD:* `uv run pytest --cov` reports ≥ 85 % (AC5).
- [ ] **TC.2** `ruff check` clean at every commit. — *DoD:* 0 violations (AC6).
- [ ] **TC.3** Every file ≤ 150 code lines; split when approaching limit. — *DoD:* AC7.
- [ ] **TC.4** No hardcoded host/port/timeout/key in source. — *DoD:* AC8.
- [ ] **TC.5** Maintain `README.md` with all mandatory sections (guidelines §2.1):
      installation instructions (step-by-step, env setup), usage instructions (all run
      modes, flags, typical workflow), examples & screenshots, configuration guide
      (every `setup.json` field explained), contribution guidelines (code style, PR
      process), license & credits. — *DoD:* README passes the §2.1 checklist.
- [ ] **TC.6** Maintain `docs/PROMPTS.md` (prompt-engineering log): add an entry for each
      significant LLM interaction during development. — *DoD:* file non-empty; entries
      include context, prompt, output, and lessons learned.
- [ ] **TC.7** Document edge cases, architecture diagrams, and match logs in `results/`
      and `assets/`. — *DoD:* at least one annotated match log and one architecture diagram.
- [ ] **TC.8** Create a match-analysis notebook in `notebooks/` once integration is
      complete. — *DoD:* notebook runs end-to-end; documents at least one analysis
      (e.g. move distribution, match length histogram).

---

## Open questions to resolve before Phase 4
- Exact role set and turn order for the placeholder game (drives `matchmaking` + `state`).
- Move-timeout policy: forfeit vs. skip-turn vs. retry — pick one per config.
- Anthropic model name for Phase 2 LLM brains (add to `setup.json`).
- Referee brain decision types: what rulings/actions does the referee brain need to make
  (drives `RefereeContext` and `RefereeDecision` schema in T4.7)?
