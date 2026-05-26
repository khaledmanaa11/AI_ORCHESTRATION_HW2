# PRD — Player Arsenal (judge-manipulation engine)

| Field    | Value                                       |
|----------|---------------------------------------------|
| Document | `PRD_player.md`                             |
| Project  | `agent-arena`                               |
| Version  | 1.00                                        |
| Date     | 2026-05-26                                  |
| Status   | Draft — pending approval before development |
| Author   | Khaled                                      |

> Companion documents: [PLAN_player.md](PLAN_player.md) · [TODO_player.md](TODO_player.md)
> Sibling triplet (referee side, shipped): [PRD_referee.md](PRD_referee.md)
> **Source of truth:** this PRD transcribes the locked decision ledger
> [DESIGN_LEDGER.md](DESIGN_LEDGER.md) — arsenal S4 (`[4a]`–`[4j]`), experiment S8 (`[8.1]`–`[8.15]`),
> protocol/config S7 (`[7.f]`–`[7.j]`). Each requirement cites the ledger decision it derives from —
> **no new design here.** Build-shape choices (one structured call, deterministic selector, shared
> client, A+ seed, per-process stream files) were decided in the 2026-05-26 planning session.

---

## 1. Purpose & Scope

The referee side is shipped (`PRD_referee.md`, Modules A–I.5). This triplet builds the **player's
private arsenal** — the judge-manipulation engine that turns a player process from the
deterministic `SeededPlayerBrain` placeholder `[RH1.1]` into a real LLM debater that **reads** the
judge and **exploits** its biases. This is the experiment's independent variable: the
manipulation-ON vs manipulation-OFF roster `[4j]` whose win-rate delta is the headline result
`[L3, 8.7]`.

**The thesis the arsenal must make measurable** `[4i, 8.11]`: a player wins by *reading* the judge —
exploiting **stated-vs-revealed divergence** (the rubric says Logic 30% but the broadcast tells
reveal an authority-sucker) — not by blind tool-spam. Every private cognitive artifact (the READ
profile, the chosen CONTROL vectors, the candidate drafts) must therefore be **captured** so the
analysis can correlate *what was attempted* against *whether the verdict moved* `[4a, 8.10]`.

**In scope for this triplet** — the player side only:

| Module | Class / artifact | Ledger |
|--------|------------------|--------|
| `shared/llm_client.py` | `LLMClient` factored out of the referee (shared by both) | build-shape |
| `services/player/brain/base.py` | `PlayerBrain`, `PlayerContext`, `PlayerDecision` | `[4a]` |
| `services/player/brain/player_prompts.py` | single ablation-aware structured prompt builder | `[4b]`–`[4i]` |
| `services/player/brain/output_parser.py` | parse the one call's structured JSON | build-shape |
| `services/player/brain/selector.py` | deterministic Best-of-N heuristic selector | `[4g]` |
| `services/player/brain/llm_brain.py` | `LLMPlayerBrain(PlayerBrain)` — orchestrates the one call | `[4a]`–`[4j]` |
| `services/player/brain/capture.py` | private-capture sink (stream-b writer) | `[4a, 8.10]` |
| `services/player/agent.py` | wire `LLMPlayerBrain` in; own the cross-turn scratchpad | `[4d]` |
| `config/setup.json` → `debate.player` (additions only) | LLM knobs the arsenal reads | `[7.i]` |
| `config/setup.json` → `debate.match` + `llm` (additions only) | results dir / run_id / generation seed | `[8.13]` |

**Out of scope** (explicitly deferred so this triplet stays buildable in small phases):

- The **experiment sweep runner** (cell iteration, match spawning, resumability, stream-joining) →
  that *is* Module J `[8.13]`.
- The **analysis notebook** (READ-accuracy, binomial CIs, hypotheses H1–H5) → Module J / TC.8 `[8.11, 8.15]`.
- **Real per-motion evidence-pack curation** `[4f-ii]` → a J-prep content artifact; this triplet
  ships only a small **test fixture** pack.
- **Any referee-side or protocol/transport change.** The judge is done (Modules I/I.5); the wire is
  frozen at `PROTOCOL_VERSION "1.00"` `[7.a]`. The player triplet keeps the protocol diff **zero**.

---

## 2. Problem Statement

The player process today registers, accepts a role, and on each `MOVE_REQUEST` emits a seeded
placeholder string `[RH1.1]`. To run the centerpiece experiment we need a player that, **inside its
own process and never on the wire** `[4a]`:

1. builds a structured model of the live judge from broadcast tells + the stated rubric (READ, `[4c]`);
2. generates several candidate utterances that exploit the inferred susceptibilities (CONTROL, `[4b]`),
   subject to an ablation switch that can disable all or individual exploits `[4j, 7.j]`;
3. selects the most judge-exploiting candidate (Best-of-N, `[4g]`);
4. carries a private cross-turn scratchpad of lessons (Reflexion, `[4d]`);
5. emits exactly one public field — the chosen utterance `[4a, 5.7a]`;
6. dumps its private reasoning trace to the results log **post-game, out-of-band** `[4a, 8.10]`.

All of this must run **offline-testable** (free Gemini key, rate-limited → cost is the constraint),
**reproducibly** `[1e, 4f]`, and **without touching the protocol layer** `[7.a]`.

---

## 3. Build-shape decisions (planning session 2026-05-26)

These bind the requirements below. They are implementation choices on top of the frozen design, not
new design.

- **BS-1 · One structured Gemini call per turn.** The whole private pipeline (READ + persona +
  CONTROL drafting + Reflexion) is expressed in a **single** call whose output is **structured JSON**
  (`read_profile`, `reflexion_lesson`, `candidate_drafts[]`), not plain text. Rationale: rate limits
  are the binding constraint; a literal multi-call pipeline (~8+ calls/turn) makes the ~250–400-match
  sweep `[8.13]` infeasible on the free tier. Structured output preserves the measurable artifacts
  `[4a, 8.10, 8.11]` at one call's cost.
- **BS-2 · Deterministic Best-of-N selector.** Candidate selection is **pure Python**, not an LLM
  call `[4g]`. The model emits N drafts (each tagged with the vectors it targets); a deterministic
  heuristic scores each draft and picks one. No mock-judge LLM call.
- **BS-3 · Shared LLM client.** The referee's `gemini_client.py` is factored to
  `shared/llm_client.py` so referee and player share one client and one fake-injection seam.
- **BS-4 · A+ reproducibility.** If the Gemini generation config exposes a `seed`, the player passes
  the match seed for near-deterministic output; otherwise `temperature`/`top_p` are fixed in config
  and reproducibility is statistical (K mirror pairs, CIs) `[8.13]`. The selector is always
  deterministic; the brain is stateless and the agent owns the scratchpad `[4d, 6.d-analogue]`.
- **BS-5 · Per-process stream files, post-game buffered dump.** Private capture buffers in the agent
  during the match and dumps once at `GAME_OVER` to `results/<run_id>/<match_id>.player_<side>.jsonl`,
  symmetric with the judge's post-game trajectory dump `[6.d]` and matching `[4a]`'s "out-of-band,
  post-game" rule. Each process writes its own stream file; the J runner joins on
  `(match_id, seed, turn_number)` `[8.10]`.

---

## 4. Functional Requirements

### 4.1 Player-brain contract (FR-PB)

- **FR-PB1 · Abstract `PlayerBrain`.** A stateless abstract base mirroring `RefereeBrain` `[6.0]`,
  with a single method `generate(context: PlayerContext) -> PlayerDecision`. Holds **no** mutable
  match state and makes **no** state-carrying assumptions across calls `[4d, 6.d-analogue]`.
- **FR-PB2 · `PlayerContext` (in).** `{ state (public DebateState.to_dict(), `[5.4e]`), legal_moves
  (the single constraint descriptor, `[5.7b]`: turn_number/side/phase/word_cap/must_engage/attempt/
  max_attempts), rubric (criteria+weights, from ROLE_ASSIGN, `[1e, 7.g]`), evidence_pack (`[4f, 7.f]`),
  side, ablation (the `debate.player.ablation` block, `[7.j]`), scratchpad (prior-turn lessons +
  prior READ profiles, agent-owned, `[4d]`), seed }`. The context is **player-process-internal and
  never hits the wire**.
- **FR-PB3 · `PlayerDecision` (out).** `{ move: {text}` (the one public field, ≤ word_cap, `[5.7a]`)`,
  trace: {...}` (the private-capture record for this turn, `[4a]`) }`. Only `move` ever reaches the
  wire (via `MOVE_SUBMIT`); `trace` is buffered for the post-game dump (BS-5).
- **FR-PB4 · `SeededPlayerBrain` conforms.** The existing placeholder `[RH1.1]` is adapted to the
  same base so the offline integration path and determinism guarantees survive.

### 4.2 READ — structured judge profiling (FR-RD) `[4c]`

- **FR-RD1 · Structured profile, not prose.** Each turn the call returns a `read_profile` =
  `{ revealed_criterion_emphasis, susceptibility:{sycophancy, authority, bandwagon, fallacy} (0–1),
  style_notes }` `[4c]`. `style_notes` carries the folded-in self-preference mirror (judge diction/
  structure) `[4b, 4c]`.
- **FR-RD2 · Inputs only from public + setup.** The profile is inferred from broadcast tells (read
  off `state.transcript`, `[5.4c, 7.b]`), the stated rubric+weights `[1e]`, and the full transcript —
  **no numbers** (numbers are off-wire until verdict, `[2a, 5.4e]`).
- **FR-RD3 · Online cadence + cold start.** The profile is re-inferred every turn as tells accrue;
  turn 1 (PRO opening) has zero tells → READ runs on rubric **priors** only `[4c]`.
- **FR-RD4 · READ→CONTROL coupling gated by `read_targeting`.** When `read_targeting` is ON, the
  prompt aims the enabled CONTROL vectors at the profile's top inferred susceptibility (exploiting
  stated-vs-revealed divergence, `[4c, 4i]`). When OFF, the profile is still built (β still adapts
  substantively) but is **not** used to aim exploits.

### 4.3 CONTROL — the manipulation spine (FR-CT) `[4b]`

- **FR-CT1 · Four toggleable CONTROL vectors.** The prompt can instruct candidate drafts to deploy
  **(1) Sycophancy** (reflect the judge's tells/values back, escalate one-sided framing),
  **(2) Authority** (confident credentialed sourcing; under the closed-book pack this becomes
  *fabricated* authority, `[4f]`), **(3) Bandwagon** (claimed consensus/social proof),
  **(4) Fallacy-oversight** (smuggle subtle fallacies the opponent must catch) `[4b]`. Each vector is
  independently gated by `debate.player.ablation.vectors.<name>` `[7.j]`.
- **FR-CT2 · Verbosity = always-on bounded lever.** "Maximum structured density within the word cap"
  is a framing default, not a discrete tool `[4b]`; raw length is equalized by the cap `[1c]`.
- **FR-CT3 · Persona/Sentiment gated by `adaptive_persona`.** When ON, the prompt selects an advocate
  voice from a small enumerated `persona_set` keyed by the READ profile (authoritative-academic /
  plain-spoken / passionate / …), expressing the folded-in Sentiment + self-preference mirror
  `[4h, 4c]`. When OFF, a neutral persona is used. **Conviction** (total commitment to the assigned
  side, no hedging) is always on, both arms `[4h]`.
- **FR-CT4 · Each draft is vector-tagged.** Every candidate draft carries a `targets` list naming the
  vectors it deploys, so the selector (FR-BN) and the trace (FR-PC) can attribute the effect `[8.10]`.

### 4.4 Reasoning spine — Reflexion + scratchpad (FR-RX) `[4d]`

- **FR-RX1 · Within-turn critique-revise, cap 1.** The single call performs an internal draft →
  self-critique vs rubric+profile+legality → revise, expressed as the prompt asking for already-
  revised candidates (cap 1 cycle, config-mirrors the `[3b]` retry cap) `[4d]`.
- **FR-RX2 · Across-turn lesson.** The call returns a `reflexion_lesson` (e.g. "authority flagged
  unverifiable → pivot to checkable evidence") which the **agent appends to the scratchpad** and
  injects into the next turn's `PlayerContext` `[4d]`. The brain stays stateless (FR-PB1); the agent
  owns the scratchpad.
- **FR-RX3 · Reflexion runs on both ablation arms.** Reflexion is competence, not manipulation → it
  is ON for both β baseline and ON roster so both conditions are equally competent reasoners; only
  manipulation differs `[4d, 4j]`.

### 4.5 Best-of-N — deterministic selection (FR-BN) `[4g]`

- **FR-BN1 · N candidate drafts from one call.** The call emits `best_of_N` candidate drafts
  (config `debate.player.best_of_N`, default 3) `[4g, 7.i]`.
- **FR-BN2 · Selection is pure Python (BS-2).** A deterministic heuristic scores each draft and picks
  the highest; no LLM call. Ties broken deterministically (lowest index) for reproducibility.
- **FR-BN3 · Two selection modes gated by `bestN_judge_select`** `[4g, 7.j]`:
  - **judge-profile mode (ON):** score = match of each draft's `targets` against the READ profile
    susceptibilities (FR-RD1), weighted by the rubric weights — i.e. the player *mock-judges* each
    draft against its own judge-model and picks the most judge-exploiting shot `[4g]`.
  - **rubric-quality mode (OFF, the β baseline):** score = rubric-quality heuristic only (no
    susceptibility weighting) — competence selection, off the manipulation axis `[4g, S4 close]`.
- **FR-BN4 · The selected draft's `text` is the public move.** Discarded drafts go to the trace
  (FR-PC), never to the wire `[4a]`.

### 4.6 Ablation switch (FR-AB) `[4j, 7.j]`

- **FR-AB1 · Master + per-vector + baseline_mode read from config.** The brain reads
  `debate.player.ablation` = `{ master, vectors{sycophancy, authority, bandwagon, fallacy,
  adaptive_persona, bestN_judge_select, read_targeting}, baseline_mode }` `[7.j]`. No code edit per
  condition (AC8) — the sweep is pure config `[8.13]`.
- **FR-AB2 · OFF roster (master=false).** Prompt instructs honest substantive adaptation to tells +
  rubric (β) `[4j]`: Reflexion + Steelman + Conviction + rubric-awareness + honest evidence-pack
  citing + verbosity-density + Best-of-N **rubric-quality** selection + neutral persona. **No
  exploit instructions; drafts carry empty `targets`.** `[S4 close roster]`
- **FR-AB3 · ON roster (master=true).** Adds, per enabled vector: the 4 CONTROL tools + fabricated
  authority + Best-of-N **judge-profile** selection + adaptive judge-driven persona + READ-targeting
  `[S4 close roster]`.
- **FR-AB4 · baseline_mode β | α.** β (default): OFF reads tells and adapts substantively. α
  (optional): OFF ignores tells entirely (deaf baseline) `[4j, 8.12]`. Both players read the
  identical ablation block (symmetry, `[L4]`).

### 4.7 Private capture (FR-PC) `[4a, 8.10]`

- **FR-PC1 · Per-turn trace record.** `{ match_id, seed, turn_number, side, phase, read_profile,
  selected_vectors (chosen draft's targets ∩ enabled vectors), candidate_drafts (all N, each with
  text+targets), selected_draft_index, reflexion_lesson, ablation_cell }` `[8.10 stream b]`.
- **FR-PC2 · Buffered, post-game dump (BS-5).** Records buffer in the agent during the match; on
  `GAME_OVER` they dump to `results/<run_id>/<match_id>.player_<side>.jsonl`. Never to the opponent,
  never to the judge mid-game `[4a]`.
- **FR-PC3 · Shared join keys.** Every record carries `match_id`, `seed`, `turn_number` so the J
  runner can join stream b against the referee's stream a `[8.10]`.
- **FR-PC4 · Gated by `private_capture`.** When `false`, no trace is written (pure black-box wire
  behavior) `[4a]`.

### 4.8 Evidence grounding (FR-EV) `[4f]`

- **FR-EV1 · Shared pack consumed from setup.** The player reads the identical evidence pack from
  `ROLE_ASSIGN.game_config["evidence_pack"]` `[4f, 7.f]`; closed-book relative to that corpus, no live
  retrieval.
- **FR-EV2 · Honest vs fabricated citing follows the ablation.** β cites the pack honestly; the ON
  Authority vector may **fabricate** authority (cite a source not in the pack) `[4b, 4f]` — the
  detectable exploit the structural judge (Arm-3) is built to catch.
- **FR-EV3 · Fixture pack only.** This triplet ships a small fixture pack for tests; real per-motion
  curation is deferred `[4f-ii]`.

---

## 5. Acceptance Criteria

| ID | Criterion | Ledger / source |
|----|-----------|-----------------|
| PL-AC1 | **Zero protocol diff.** `git diff src/agent_arena/services/protocol/` is empty; `PROTOCOL_VERSION` stays `"1.00"`. The only public field emitted is `move.text`. | `[7.a, 5.7a]` |
| PL-AC2 | **One Gemini call per turn.** A full turn invokes the LLM client exactly once; selection adds zero calls. | BS-1, BS-2 |
| PL-AC3 | **Offline tests.** No test imports `google.generativeai` or constructs a real client; a fake `LLMClient` is injected. Coverage ≥ 85 %. | BS-3, `[8.13]` |
| PL-AC4 | **Ablation is pure config.** Flipping `debate.player.ablation` changes the assembled prompt + selection mode with **no source edit**; OFF roster ≠ ON roster (asserted structurally). | `[7.j, 8.13]` |
| PL-AC5 | **Attributable trace.** With `private_capture=true`, each turn produces a stream-b record with the FR-PC1 fields and the shared join keys; the post-game dump lands at the BS-5 path. | `[4a, 8.10]` |
| PL-AC6 | **Stateless brain.** `LLMPlayerBrain` holds no per-match mutable state; cross-turn memory lives in the agent scratchpad and is injected via `PlayerContext`. | `[4d]`, BS-4 |
| PL-AC7 | **Reproducibility.** Same seed ⇒ identical structural choices; if the generation `seed` is supported it is passed; `temperature`/`top_p` come from config. | BS-4, `[1e, 4f]` |
| PL-AC8 | **No hardcoded operational values.** `best_of_N`, temperature, top_p, persona set, selector weights, results dir, run_id all from config/constants — no magic strings. | `[AC8]` |
| PL-AC9 | **≤150 code lines per source file.** Every new file respects the cross-cutting cap (Module K). | `[K]` |

---

## 6. Non-Goals

- Not building the sweep runner, the analysis notebook, or computing READ-accuracy — those consume
  this triplet's output in Module J `[8.11, 8.13]`.
- Not curating real evidence packs `[4f-ii]`.
- Not changing the judge, the engine, the protocol, or matchmaking.
- Not guaranteeing the LLM *actually manipulates well* — prompt content quality is validated
  **empirically in J's sweep** `[8.15]`, not by unit tests (which assert prompt *structure*).
