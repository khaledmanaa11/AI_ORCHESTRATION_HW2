# Architecture Plan — Player Arsenal

| Field    | Value                                       |
|----------|---------------------------------------------|
| Document | `PLAN_player.md`                            |
| Project  | `agent-arena`                               |
| Version  | 1.00                                        |
| Date     | 2026-05-26                                  |
| Status   | Draft                                       |

> Companion: [PRD_player.md](PRD_player.md) · [TODO_player.md](TODO_player.md)
> Decisions source: [DESIGN_LEDGER.md](DESIGN_LEDGER.md) (S4 arsenal, S8 experiment) + the 2026-05-26
> build-shape decisions (BS-1…BS-5 in the PRD).
> **No source code in this document — structure, interfaces in prose, and diagrams only.**

---

## 1. Overview

The player process specializes the substrate at one seam: the **brain**. Today `PlayerAgent` holds a
`SeededPlayerBrain` `[RH1.1]` and, on each `MOVE_REQUEST`, emits a placeholder string. This triplet
replaces that with a real `LLMPlayerBrain` that runs the full private arsenal in **one structured
Gemini call per turn** (BS-1), selects a candidate deterministically (BS-2), and dumps a private
trace post-game (BS-5). The wire contract is unchanged — the brain still produces exactly one public
field, `move.text` `[5.7a, 7.a]`.

Mirrors the proven referee architecture: an abstract `PlayerBrain.generate(context)->decision`
contract `[6.0-analogue]`, a placeholder impl (`SeededPlayerBrain`) and an LLM impl
(`LLMPlayerBrain`), with the LLM client factored to `shared/` so referee and player share one seam
(BS-3). The **brain is stateless**; the **agent owns** the cross-turn scratchpad and injects it each
turn (BS-4), exactly the `[6.d]` pattern the referee loop uses for its trajectory.

```
        ┌──────────────────────────── Player process ─────────────────────────────┐
        │                                                                          │
 wire ─►│  PlayerAgent (owns scratchpad: prior lessons + prior READ profiles)      │
 MOVE_  │     │  builds PlayerContext { state, legal_moves, rubric, evidence_pack, │
 REQUEST│     │                         side, ablation, scratchpad, seed }         │
        │     ▼                                                                    │
        │  LLMPlayerBrain.generate(ctx)                                            │
        │     │                                                                    │
        │     │ player_prompts.build(ctx)  ──► ONE structured Gemini call          │
        │     │     (ablation-aware: READ + persona + CONTROL + Reflexion)         │
        │     │                              │                                     │
        │     │ output_parser.parse(json) ◄──┘  { read_profile, reflexion_lesson,  │
        │     │     │                              candidate_drafts:[{text,targets}]}│
        │     │     ▼                                                              │
        │     │ selector.pick(drafts, profile, rubric, mode)   (pure Python, BS-2) │
        │     │     │  mode = judge-profile (ON) | rubric-quality (OFF)            │
        │     │     ▼                                                              │
        │     └─► PlayerDecision { move:{text}=chosen.text,  trace:{...} }          │
        │           │                          │                                   │
        │  MOVE_SUBMIT ◄── move.text           └─► agent buffers trace;            │
        │  (only public field)                     agent appends lesson→scratchpad │
        │                                                                          │
        │  on GAME_OVER:  capture.dump(buffer) ─► results/<run>/<match>.player_<s>.jsonl
        └──────────────────────────────────────────────────────────────────────────┘
```

The judge never sees any of the private boxes — it scores only `move.text` `[4a(i)]`. The opponent
sees only the public transcript + tells `[4a(iii)]`.

---

## 2. File Structure (new + touched)

```
src/agent_arena/shared/
├── llm_client.py        ← LLMClient, factored from referee/brain/gemini_client.py   (MOVED, P0)
│                          (referee llm_brain.py import updated to the shared path)

src/agent_arena/services/player/brain/
├── seeded_brain.py      ← existing placeholder, adapted to PlayerBrain base         (TOUCHED, P1)
├── base.py              ← PlayerBrain (ABC), PlayerContext, PlayerDecision          (NEW, P1)
├── player_prompts.py    ← single structured prompt builder, ablation-aware          (NEW, P2)
├── output_parser.py     ← parse structured JSON → profile / drafts / lesson         (NEW, P3)
├── selector.py          ← deterministic Best-of-N heuristic, two modes              (NEW, P4)
├── llm_brain.py         ← LLMPlayerBrain(PlayerBrain): build→1 call→parse→select    (NEW, P5)
└── capture.py           ← private-capture sink (stream-b JSONL writer)              (NEW, P6)

src/agent_arena/services/player/
└── agent.py             ← wire LLMPlayerBrain; own scratchpad; buffer+dump trace     (TOUCHED, P7)

config/setup.json        ← debate.player (+ temperature/top_p/persona_set/selector_weights),
│                          debate.match (+ run_id/results_dir), llm (+ generation_seed)  (TOUCHED, P2/P5/P6)
src/agent_arena/constants.py ← new config-key + persona + selector-weight default tokens  (TOUCHED)

config/fixtures/evidence_pack_test.json  ← small fixture pack for offline tests      (NEW, P2)

services/protocol/**     ← UNTOUCHED (PL-AC1)
services/referee/**      ← UNTOUCHED except the gemini_client import move (P0)
```

If any file would exceed ~150 code lines (PL-AC9), split it (e.g. `player_prompts.py` into a
section-assembler + a vector-catalog, like the referee's `judge_prompts.py`).

---

## 3. The seams in prose

### 3.1 `PlayerBrain` / `PlayerContext` / `PlayerDecision` (P1)

`PlayerBrain` is an abstract base with one method, `generate(context) -> decision`, mirroring
`RefereeBrain.decide` `[6.0]`. It is **stateless**: same context in ⇒ same structural decision out
(modulo LLM sampling, which BS-4 pins via config/seed). `PlayerContext` is a frozen dataclass
carrying everything the brain needs (PRD FR-PB2); critically it carries the **agent-owned
scratchpad** (prior lessons + prior profiles) so cross-turn memory never lives in the brain.
`PlayerDecision` carries the one public `move` and the private `trace`; the agent routes `move` to
`MOVE_SUBMIT` and buffers `trace`. `SeededPlayerBrain` is adapted to implement `generate` (ignoring
the LLM fields), keeping the offline integration path and determinism guarantees alive.

### 3.2 The single prompt (P2) — ablation-aware assembly

`player_prompts.build(context)` assembles one prompt from sections, gated by the ablation block
(FR-AB), analogous to how `judge_prompts.build_turn_prompt` branches on `judge_variant`:

- **Always:** motion, side, phase, word cap, must-engage flag, the stated rubric+weights, the
  evidence pack, the prior reflexion lessons, and an instruction to return **structured JSON** with
  `read_profile`, `reflexion_lesson`, and `best_of_N` `candidate_drafts` (each `{text, targets}`).
- **β / OFF roster (master=false):** honest substantive adaptation to tells + rubric; Reflexion +
  Steelman + Conviction + honest pack citing + verbosity-density. Drafts carry empty `targets`.
- **ON roster (master=true):** add, per enabled vector, the CONTROL instructions (sycophancy /
  authority-incl-fabrication / bandwagon / fallacy-oversight), adaptive persona selection from
  `persona_set` (if `adaptive_persona`), and READ-targeting of the inferred top susceptibility (if
  `read_targeting`). Drafts tag the vectors they deploy.
- **baseline_mode α:** the β branch with tell-reading suppressed (deaf baseline) `[8.12]`.

The builder returns a prompt **string** plus the generation parameters (temperature, top_p, optional
seed) read from config; it makes **no** LLM call itself (testable in isolation by asserting which
sections are present/absent — PL-AC4).

### 3.3 Structured-output parser (P3)

`output_parser.parse(raw)` turns the model's JSON into a typed `ParsedTurn`
(`read_profile`, `reflexion_lesson`, `candidate_drafts`). It is defensive: malformed JSON or missing
fields fall back to a **single safe honest draft** (so a bad generation degrades to a weak legal
turn, never a crash — consistent with `[4a(ii)]` "reasoning dumped into the utterance is just a weak
public turn"). Pure function → fully unit-testable.

### 3.4 Deterministic selector (P4)

`selector.pick(drafts, read_profile, rubric_weights, mode, selector_weights) -> index` is the
Best-of-N heuristic (BS-2, FR-BN). Two modes:

- **judge-profile (ON):** score(draft) = Σ over the draft's `targets` of
  `susceptibility[vector] × selector_weights[vector]`, plus a rubric-weight term — i.e. reward the
  draft that best exploits the inferred live susceptibilities. The player *simulates the judge*
  deterministically `[4g]`.
- **rubric-quality (OFF):** score(draft) = a rubric-quality heuristic only (e.g. coverage of the 4
  criteria, density within cap) — no susceptibility weighting.

Ties → lowest index (reproducible, PL-AC7). Pure function, table-driven tests.

### 3.5 `LLMPlayerBrain` (P5)

Orchestrates one turn: `build → one client call → parse → select → assemble PlayerDecision`. It owns
**no** match state (PL-AC6). It reads `best_of_N`, generation params, persona set, selector weights,
and selection mode from config + the injected ablation block. The `trace` it returns contains the
full FR-PC1 record (all N drafts, chosen index, selected vectors, profile, lesson). This is the only
module that touches the LLM client, and it does so through the injected `shared.llm_client.LLMClient`
(BS-3) so tests swap in a fake.

### 3.6 Capture sink (P6)

`capture.dump(records, run_id, results_dir, match_id, side)` writes the buffered per-turn records to
`results/<run_id>/<match_id>.player_<side>.jsonl`, one JSON object per line (BS-5, FR-PC). Creates
the run directory if absent. Gated by `private_capture` (FR-PC4). The runner (Module J) later joins
these files against the referee's `*.referee.jsonl` on `(match_id, seed, turn_number)` `[8.10]`.

### 3.7 Agent wiring (P7)

`PlayerAgent` gains: a scratchpad (list of prior lessons + prior profiles), construction of
`PlayerContext` from the `MOVE_REQUEST` payload + `ROLE_ASSIGN` setup (rubric, evidence pack,
ablation), a call to `LLMPlayerBrain.generate`, routing `decision.move` to `MOVE_SUBMIT`, appending
`decision.trace.reflexion_lesson` + `read_profile` to the scratchpad, buffering `decision.trace`, and
calling `capture.dump` on `GAME_OVER`. The brain choice (seeded vs LLM) is config/constructor-driven
so the Module-H integration path (seeded) still works.

---

## 4. Reproducibility & determinism (BS-4)

- **Structural determinism** (side assignment, first_speaker, motion, pack, ablation cell) is seeded
  upstream and unchanged here `[1e, 4f]`.
- **Selector** is fully deterministic (pure function, lowest-index tie-break).
- **Generation:** if the Gemini config exposes a `seed`, `LLMPlayerBrain` passes the match seed →
  near-deterministic drafts (A+). Otherwise `temperature`/`top_p` are fixed in config and run-to-run
  text varies; the experiment absorbs this statistically (K mirror pairs + CIs, `[8.13]`).
- **Brain statelessness** keeps replays clean: re-running a turn with the same context + same seed
  yields the same decision path.

---

## 5. Testing strategy (offline, PL-AC3)

- A **fake `LLMClient`** (constructor-injected, the BS-3 seam) returns canned structured JSON per
  scenario — the single offline seam shared with the referee tests.
- **Deterministic scaffold = the coverage surface** (table-driven):
  - `selector.pick` — `(profile, drafts, mode) → expected index`, incl. tie-break.
  - `player_prompts.build` — assert sections present/absent per master / per-vector / baseline_mode;
    assert **OFF roster ≠ ON roster** (structural, like `test_llm_brain.py`).
  - `output_parser.parse` — valid JSON, malformed JSON (→ safe-draft fallback), missing fields.
  - `capture.dump` — correct path, one line per turn, FR-PC1 fields + join keys present; skipped when
    `private_capture=false`.
  - stateless brain + agent scratchpad — a prior lesson is carried into the next context;
    `SeededPlayerBrain` still deterministic.
- **One integration test:** a full player turn with the fake client → `PlayerDecision{move, trace}`,
  mirroring the Module-H referee integration test `[H]`.
- **Out of test scope (stated honestly):** whether the LLM *manipulates well* — that is validated
  empirically in J's sweep `[8.15]`. Tests assert prompt **structure**, not LLM output quality.
- **Gate guard:** a test asserts no module under test imports `google.generativeai` or builds a real
  client.

---

## 6. Dependency order

`P0 (shared client) → P1 (base) → P2 (prompts) → P3 (parser) → P4 (selector) → P5 (LLM brain) →
P6 (capture) → P7 (agent wiring + integration)`. K (cross-cutting gates) asserted after every phase.
P5 depends on P2–P4; P7 depends on P5–P6. P0 is a pure refactor that must leave the referee suite
green before anything else proceeds.
