# Task Tracking — Player Arsenal

| Field    | Value                                       |
|----------|---------------------------------------------|
| Document | `TODO_player.md`                            |
| Project  | `agent-arena`                               |
| Version  | 1.00                                        |
| Date     | 2026-05-26                                  |

---

## ⚡ NEXT-SESSION HANDOFF (pick up here)

**Sibling triplet (referee) complete:** Modules A → I.5 (latest `0053d55`, pushed).
**This triplet (player arsenal) status:** Module P1 completed.

**Start with Module P2** — single prompt builder (`services/player/brain/player_prompts.py`). Then P3 → P7 in order.

**Build order reminder:** `P0 → P1 → P2 → P3 → P4 → P5 → P6 → P7`, K asserted after every phase.
Commit after each phase passes the gate. One phase per commit; developer never pushes.

---

> Status: `[ ]` not started · `[~]` in progress · `[x]` done
> Every task maps to a requirement in [PRD_player.md](PRD_player.md) and a ledger decision in
> [DESIGN_LEDGER.md](DESIGN_LEDGER.md). Companion: [PLAN_player.md](PLAN_player.md).
> **Cross-cutting rules (assert per phase, Module K):** every source file ≤ 150 code lines,
> `ruff check src tests` clean, coverage ≥ 85 %, no hardcoded operational values, no magic strings,
> **`git diff src/agent_arena/services/protocol/` empty (PL-AC1)**, no test hits the network (PL-AC3).
> **Commit cadence:** one commit per completed phase (a `P*` section), only after its tests + `ruff`
> pass — see the build order at the bottom.

---

## Module P0 — Shared LLM client · `shared/llm_client.py` (BS-3)  `[x]`

### P0.1 — Move the client
- [x] **RP0.1** Move `services/referee/brain/gemini_client.py` → `shared/llm_client.py` (rename class
  to `LLMClient` if currently Gemini-specific; keep the same public method signature).
  - *DoD:* file exists at the new path; old path removed.
- [x] **RP0.2** Update the referee import (`services/referee/brain/llm_brain.py`) to the shared path.
  - *DoD:* `grep -r gemini_client src` returns nothing; referee imports `shared.llm_client`.

### P0.2 — Keep referee green
- [x] **RP0.3** Run the full referee suite; fix only import paths (no behavior change).
  - *DoD:* `uv run pytest -q` 0 failures; `git diff --stat` shows only import-line changes + the move.
  - *DoD:* protocol diff empty (PL-AC1).

---

## Module P1 — Player-brain contract · `services/player/brain/base.py` (FR-PB) `[4a]`  `[x]`

### P1.1 — Dataclasses
- [x] **RP1.1** Define frozen `PlayerContext` with the FR-PB2 fields (state, legal_moves, rubric,
  evidence_pack, side, ablation, scratchpad, seed).
  - *DoD:* immutable; carries no wire-only concerns.
- [x] **RP1.2** Define `PlayerDecision` = `{move: dict, trace: dict}` (move = `{"text": ...}`).
  - *DoD:* `move` holds exactly one public field (PL-AC1 / `[5.7a]`).

### P1.2 — Abstract base + placeholder conformance
- [x] **RP1.3** Define abstract `PlayerBrain` with `@abstractmethod generate(context)->PlayerDecision`;
  stateless (no mutable attrs) (FR-PB1).
  - *DoD:* instantiating the ABC raises; subclasses must implement `generate`.
- [x] **RP1.4** Adapt `SeededPlayerBrain` `[RH1.1]` to subclass `PlayerBrain.generate` (deterministic
  text, empty trace) (FR-PB4).
  - *DoD:* same seed ⇒ identical output; existing seeded tests still pass.

---

## Module P2 — Single prompt builder · `services/player/brain/player_prompts.py` (FR-RD/CT/RX/AB) `[ ]`

### P2.1 — Structured-output contract
- [ ] **RP2.1** Define the required JSON output shape in the prompt: `{read_profile, reflexion_lesson,
  candidate_drafts:[{text, targets}]}` with `best_of_N` drafts (FR-BN1, FR-RD1, FR-RX2).
  - *DoD:* the prompt explicitly requests this schema; N read from config.

### P2.2 — Ablation-aware section assembly
- [ ] **RP2.2** Assemble the always-on sections (motion, side, phase, word cap, must-engage, rubric,
  evidence pack, prior lessons) (FR-PB2, FR-EV1).
  - *DoD:* present regardless of ablation.
- [ ] **RP2.3** β / OFF-roster branch (master=false): honest adaptation, no exploit instructions,
  empty `targets` (FR-AB2).
  - *DoD:* no CONTROL vocabulary appears.
- [ ] **RP2.4** ON-roster branch (master=true): per-enabled-vector CONTROL instructions
  (sycophancy / authority+fabrication / bandwagon / fallacy), adaptive persona (if
  `adaptive_persona`), READ-targeting (if `read_targeting`) (FR-CT1/3, FR-RD4, FR-AB3).
  - *DoD:* a disabled vector's instruction is absent; OFF roster ≠ ON roster (asserted, PL-AC4).
- [ ] **RP2.5** baseline_mode α branch: β with tell-reading suppressed (FR-AB4) `[8.12]`.
  - *DoD:* α prompt omits the tell-adaptation section.
- [ ] **RP2.6** Return `(prompt_str, generation_params)` where params (temperature, top_p, optional
  seed) come from config; **no LLM call here** (BS-1).
  - *DoD:* builder is a pure function of context + config.
- [ ] **RP2.7** Add the fixture evidence pack `config/fixtures/evidence_pack_test.json` (FR-EV3).
  - *DoD:* small, real-shaped; used only by tests.

*(If this file exceeds ~150 lines, split into a section-assembler + a vector-catalog module — PL-AC9.)*

---

## Module P3 — Output parser · `services/player/brain/output_parser.py` (BS-1)  `[ ]`

- [ ] **RP3.1** `parse(raw) -> ParsedTurn{read_profile, reflexion_lesson, candidate_drafts}`.
  - *DoD:* well-formed JSON parses into the typed shape.
- [ ] **RP3.2** Defensive fallback: malformed JSON / missing fields → a single safe honest draft +
  empty profile/lesson (never raises) `[4a(ii)]`.
  - *DoD:* a garbage string yields one legal draft, not an exception.
- [ ] **RP3.3** Normalize each draft to `{text:str, targets:list[str]}` (default `targets=[]`).
  - *DoD:* drafts missing `targets` get `[]`.

---

## Module P4 — Deterministic Best-of-N selector · `services/player/brain/selector.py` (FR-BN, BS-2) `[ ]`

- [ ] **RP4.1** `pick(drafts, read_profile, rubric_weights, mode, selector_weights) -> int` (pure).
  - *DoD:* no LLM call; deterministic.
- [ ] **RP4.2** judge-profile mode: score = Σ_targets `susceptibility[v]·selector_weights[v]` + rubric
  term; pick max (FR-BN3 ON) `[4g]`.
  - *DoD:* the draft targeting the highest-susceptibility vector wins on a crafted case.
- [ ] **RP4.3** rubric-quality mode: rubric-quality heuristic only, no susceptibility weighting
  (FR-BN3 OFF).
  - *DoD:* susceptibility changes do not change the pick in this mode.
- [ ] **RP4.4** Tie-break = lowest index (PL-AC7).
  - *DoD:* equal scores → smallest index returned.

---

## Module P5 — LLM player brain · `services/player/brain/llm_brain.py` (FR-PB, FR-PC) `[ ]`

- [ ] **RP5.1** `LLMPlayerBrain(PlayerBrain)` takes an injected `LLMClient` + config; holds **no**
  match state (PL-AC6, FR-PB1).
  - *DoD:* no per-match mutable attributes.
- [ ] **RP5.2** `generate(ctx)` = build prompt (P2) → **one** client call (PL-AC2) → parse (P3) →
  select (P4) using mode from `bestN_judge_select` (FR-BN3).
  - *DoD:* exactly one client invocation per call (asserted with a counting fake).
- [ ] **RP5.3** Assemble `PlayerDecision`: `move={"text": chosen.text}`; `trace` = FR-PC1 record
  (match_id, seed, turn_number, side, phase, read_profile, selected_vectors = chosen.targets ∩
  enabled vectors, candidate_drafts, selected_draft_index, reflexion_lesson, ablation_cell).
  - *DoD:* trace has all FR-PC1 fields + join keys (PL-AC5).
- [ ] **RP5.4** Read `best_of_N`, temperature, top_p, generation seed, persona_set, selector_weights
  from config/constants — none hardcoded (PL-AC8).
  - *DoD:* a config change is reflected without code edit.

---

## Module P6 — Private-capture sink · `services/player/brain/capture.py` (FR-PC, BS-5) `[ ]`

- [ ] **RP6.1** `dump(records, run_id, results_dir, match_id, side)` → writes
  `results/<run_id>/<match_id>.player_<side>.jsonl`, one JSON object per line.
  - *DoD:* file at the exact BS-5 path; line count == turns.
- [ ] **RP6.2** Create the run directory if absent; paths from config (PL-AC8).
  - *DoD:* missing dir is created; no hardcoded path.
- [ ] **RP6.3** Gated by `private_capture` (FR-PC4).
  - *DoD:* `private_capture=false` ⇒ no file written.

---

## Module P7 — Agent wiring + integration · `services/player/agent.py` (FR-RX2, FR-PC2) `[ ]`

### P7.1 — Wire the brain
- [ ] **RP7.1** Add config/constructor-driven brain choice (seeded vs LLM); default keeps Module-H
  (seeded) path working.
  - *DoD:* seeded integration test `[H]` still green.
- [ ] **RP7.2** Build `PlayerContext` from `MOVE_REQUEST` + `ROLE_ASSIGN` (rubric, evidence_pack,
  ablation) + the agent scratchpad + seed (FR-PB2).
  - *DoD:* context carries setup data captured at ROLE_ASSIGN.
- [ ] **RP7.3** Call `generate`, route `decision.move` to `MOVE_SUBMIT`; append
  `trace.reflexion_lesson` + `read_profile` to the scratchpad (FR-RX2).
  - *DoD:* a prior lesson appears in the next turn's context.

### P7.2 — Capture lifecycle
- [ ] **RP7.4** Buffer `decision.trace` per turn; on `GAME_OVER` call `capture.dump` (FR-PC2, BS-5).
  - *DoD:* a multi-turn fake-client match produces the stream-b file with all turns.

### P7.3 — Config additions
- [ ] **RP7.5** Add to `config/setup.json`: `debate.player.{temperature, top_p, persona_set,
  selector_weights}`, `debate.match.{run_id, results_dir}`, `llm.generation_seed`; add validation
  (Module-G pattern) + constants tokens (PL-AC8).
  - *DoD:* config loads + validates; bad values rejected.

### P7.4 — Integration test
- [ ] **RP7.6** End-to-end fake-client turn → `PlayerDecision{move, trace}`; assert PL-AC1/2/3/5/6
  hold (one call, zero protocol diff, offline, trace written, brain stateless).
  - *DoD:* mirrors the Module-H referee integration test; green.

---

## Build order (dependency-ordered; one commit per phase)

`P0 → P1 → P2 → P3 → P4 → P5 → P6 → P7`, with **K asserted after every phase**.

| Step | Phase | Commit scope (suggested) | Gate | Status |
|------|-------|--------------------------|------|--------|
| 1 | P0 | `refactor(shared/llm-client)` | referee suite green; protocol diff empty | ✅ |
| 2 | P1 | `feat(player/brain-base)` | ABC + dataclass + seeded conformance tests green | ✅ |
| 3 | P2 | `feat(player/prompts)` | section-assembly + OFF≠ON + α tests green | ⏳ |
| 4 | P3 | `feat(player/output-parser)` | valid + malformed-fallback tests green | ⏳ |
| 5 | P4 | `feat(player/selector)` | both modes + tie-break tests green | ⏳ |
| 6 | P5 | `feat(player/llm-brain)` | one-call + trace-shape + stateless tests green | ⏳ |
| 7 | P6 | `feat(player/capture)` | path + gating tests green | ⏳ |
| 8 | P7 | `feat(player/agent-wiring)` | **integration: fake-client turn → decision + dumped trace** | ⏳ |

The hard gate is **step 8 (P7.6)**: a full fake-client turn produces a legal `move` and an
attributable `trace` file with zero protocol diff — proving the arsenal plugs into the existing
player loop and feeds Module J's stream b.

---

## Coverage Matrix — every PRD requirement → task(s)

| PRD ID | Covered by | PRD ID | Covered by |
|--------|------------|--------|------------|
| FR-PB1 | RP1.3, RP5.1 | FR-AB1 | RP5.4, RP7.5 |
| FR-PB2 | RP1.1, RP7.2 | FR-AB2 | RP2.3 |
| FR-PB3 | RP1.2, RP5.3 | FR-AB3 | RP2.4 |
| FR-PB4 | RP1.4 | FR-AB4 | RP2.5 |
| FR-RD1 | RP2.1, RP3.1 | FR-PC1 | RP5.3 |
| FR-RD2 | RP2.2 | FR-PC2 | RP7.4 |
| FR-RD3 | RP2.2 | FR-PC3 | RP5.3 |
| FR-RD4 | RP2.4 | FR-PC4 | RP6.3 |
| FR-CT1 | RP2.4 | FR-EV1 | RP2.2 |
| FR-CT2 | RP2.2 | FR-EV2 | RP2.4 |
| FR-CT3 | RP2.4 | FR-EV3 | RP2.7 |
| FR-CT4 | RP3.3, RP5.3 | PL-AC1 | RP0.3, RP7.6 |
| FR-RX1 | RP2.1 | PL-AC2 | RP5.2, RP7.6 |
| FR-RX2 | RP7.3 | PL-AC3 | all test DoDs |
| FR-RX3 | RP2.3 | PL-AC4 | RP2.4 |
| FR-BN1 | RP2.1 | PL-AC5 | RP5.3, RP7.4 |
| FR-BN2 | RP4.1 | PL-AC6 | RP5.1 |
| FR-BN3 | RP4.2, RP4.3, RP5.2 | PL-AC7 | RP4.4, RP5.4 |
| FR-BN4 | RP5.3 | PL-AC8 | RP5.4, RP6.2, RP7.5 |
| | | PL-AC9 | per-phase (Module K) |
