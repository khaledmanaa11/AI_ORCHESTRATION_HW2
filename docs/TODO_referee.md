# Task Tracking — Referee & Debate Game

| Field    | Value                                       |
|----------|---------------------------------------------|
| Document | `TODO_referee.md`                           |
| Project  | `agent-arena`                               |
| Version  | 1.00                                        |
| Date     | 2026-05-25                                  |

> Status: `[ ]` not started · `[~]` in progress · `[x]` done
> Every task maps to a requirement in [PRD_referee.md](PRD_referee.md) and a ledger decision
> in [DESIGN_LEDGER.md](DESIGN_LEDGER.md). Companion: [PLAN_referee.md](PLAN_referee.md).
> Aligns with the parent [TODO.md](TODO.md) Phase-4/6/7 tasks (T4.x, T6.3, T7.2).
> Cross-cutting rules apply throughout: ≤ 150 code lines/file, `ruff` clean, coverage ≥ 85 %.

---

## Module A — `services/game/debate_state.py` (S5) → parent T4.3

> Covers FR-ST1–FR-ST8.

- [ ] **RA.1** Define frozen `TurnRecord` dataclass with fields `{turn_number, side, phase, utterance, word_count, retry_count, referee_tell, referee_flag}`.
  - *DoD:* immutable; one record == one executed turn (FR-ST4).
- [ ] **RA.2** Define frozen `DebateMove` with the single field `text: str` + `to_dict()`/`from_dict()`.
  - *DoD:* `DebateMove("x").to_dict() == {"text": "x"}`; round-trips (FR-ST7, R-AC1).
- [ ] **RA.3** Define frozen `DebateState` with fields `{motion, turn_number, transcript (tuple), status, verdict, rules_snapshot}`.
  - *DoD:* fields match FR-ST2; default `turn_number=0`, `status=PENDING`, `verdict=None`.
- [ ] **RA.4** Implement derived helpers `active_side`, `phase`, `rebuttal_round` as pure functions of `turn_number` (odd→PRO; 1–2 OPENING; 2R REBUTTAL; last 2 CLOSING).
  - *DoD:* no stored phase/side; `total_turns == 2+2R+2` (FR-ST3).
- [ ] **RA.5** Implement `DebateState.to_dict()` carrying **public-only** fields (motion, counter, derived phase/side, transcript of utterances+tells+flags+word_counts, status, verdict-if-terminal).
  - *DoD:* output contains no numeric trajectory, no private reasoning (FR-ST6, R-AC2).
- [ ] **RA.6** Implement `from_dict()` for `DebateState` (lossless inverse of RA.5).
  - *DoD:* `from_dict(s.to_dict()) == s` for representative states (R-AC1).
- [ ] **RA.7** Unit tests for round-trip, derived schedule, and the public-only invariant.
  - *DoD:* a test asserts no private/number field appears in `to_dict()` output.

## Module B — `services/game/debate_engine.py` (S5) → parent T4.1/T4.2

> Covers FR-EN1–FR-EN7. Pure deterministic mechanics, **zero LLM**.

- [ ] **RB.1** Define `DebateEngine(GameEngine)` implementing the abstract interface.
  - *DoD:* mockable; no network/LLM/disk import (FR-EN7).
- [ ] **RB.2** `get_initial_state()` → `turn_number=0`, `status=PENDING`, motion set, empty transcript.
  - *DoD:* matches FR-EN6 / GAME_START.initial_state (7.h).
- [ ] **RB.3** `validate_move(state, move)` — Tier-1 mechanical: reject empty/whitespace, over-length (`word_count > word_cap`), malformed (missing/non-str `text`).
  - *DoD:* each rejection returns a distinct reason token; valid move passes (FR-EN4, 5.7c).
- [ ] **RB.4** `get_legal_moves(state)` → one-element constraint descriptor `[{type:"utterance", turn_number, side, phase, word_cap, must_engage, attempt, max_attempts}]`.
  - *DoD:* a `list[Any]` of length 1; fields match FR-EN5 / 7.e.
- [ ] **RB.5** `apply_move(state, move)` → fresh frozen `DebateState` with the move appended as a `TurnRecord`; never mutates input.
  - *DoD:* input state unchanged; `turn_number` advances by 1 (FR-EN1).
- [ ] **RB.6** Support appending a **penalized/empty** `TurnRecord` (retry-exhausted / timeout) so the counter always advances.
  - *DoD:* an empty turn still advances `turn_number` (FR-EN3, 8.1).
- [ ] **RB.7** `is_terminal(state)` → True when `turn_number == total_turns` and all turns recorded → `status=COMPLETE`.
  - *DoD:* terminal exactly at the last scheduled turn (FR-EN2).
- [ ] **RB.8** Unit tests: full schedule advance, Tier-1 rejections, immutability, terminal detection, penalized-turn path.
  - *DoD:* ≥ 85 % coverage on the engine.

## Module C — `services/referee/brain/base.py` (S6) → parent T4.7

> Covers FR-RB1–FR-RB7.

- [ ] **RC.1** Define `RequestKind` enum `{EVALUATE_TURN, RENDER_VERDICT}`.
  - *DoD:* no string literals used for request kinds (6.a).
- [ ] **RC.2** Define `RefereeContext` dataclass per FR-RB3 (`request_kind, state, move, rubric, judge_variant, evidence_pack, score_trajectory`).
  - *DoD:* `move=None` valid on RENDER_VERDICT; never serialized to the wire.
- [ ] **RC.3** Define `RefereeDecision` dataclass per FR-RB4 (`legal, flag, tell, turn_scores, verdict`), all optional-shaped.
  - *DoD:* one dataclass covers both kinds (6.c).
- [ ] **RC.4** Define abstract `RefereeBrain` with `decide(context) -> decision` and a docstring describing the two-kind dispatch + statelessness.
  - *DoD:* interface documented; mockable (T4.7 DoD, FR-RB1/RB5).

## Module D — `services/referee/brain/simple_brain.py` (S9) → parent T4.8

> Covers FR-SB1–FR-SB7. **No external calls.**

- [ ] **RD.1** Define `SimpleRefereeBrain(RefereeBrain)`; `decide` dispatches on `request_kind`.
  - *DoD:* no LLM/network/disk/clock/RNG import or call (FR-SB1, R-AC3).
- [ ] **RD.2** EVALUATE_TURN legality = deterministic concession-keyword scan against a fixed case-folded token set → `legal=False, flag="concession"`; else `legal=True`. Off-topic never flagged.
  - *DoD:* a concession utterance is illegal; a normal one is legal (FR-SB2, 9.b).
- [ ] **RD.3** Build the number-free `tell` template from public turn data only (no scores, no coaching).
  - *DoD:* the tell string contains no numeric score (FR-SB3, 9.c).
- [ ] **RD.4** Compute `turn_scores` = `round(min(word_count/word_cap, 1.0)*10, 2)`, identical across all 4 criteria; `word_count=0 → 0.0`.
  - *DoD:* pure function of public turn data; deterministic (FR-SB4, 9.d).
- [ ] **RD.5** RENDER_VERDICT: apply the 6.h aggregate (per-criterion mean → weight 30/30/25/15 → totals → winner/margin) with the fixed tiebreak (cumulative word_count, then PRO).
  - *DoD:* output is the full 2e shape; tie resolves deterministically (FR-SB5, R-AC7).
- [ ] **RD.6** Guarantee the verdict function is **total** over any trajectory (all-zero/partial/penalized) and never raises.
  - *DoD:* an all-zero trajectory yields a valid verdict, no exception (FR-SB6, 8.6).
- [ ] **RD.7** Accept-but-ignore `judge_variant` and `evidence_pack` (no defensive prompt, no grounding check).
  - *DoD:* identical output regardless of variant value (FR-SB7, 9.g).
- [ ] **RD.8** Unit tests: determinism (same input → same output), concession path, word-count scoring, total verdict, variant-invariance.
  - *DoD:* a test runs `decide` twice and asserts equality (R-AC4); ≥ 85 % coverage.

## Module E — `services/referee/game_loop.py` debate wiring (S3 + S8) → parent T4.5/T4.6

> Covers FR-MO1–FR-MO4, FR-FT1–FR-FT7. Composes existing fault primitives — no new infra.

- [ ] **RE.1** Per-turn flow: derive `active_side`, send `MOVE_REQUEST` (constraint descriptor) to the active player only.
  - *DoD:* descriptor echoes `side`+`turn_number` (5.7e); broadcast never used for MOVE_REQUEST.
- [ ] **RE.2** On received move: run `engine.validate_move` (Tier-1) then `brain.decide(EVALUATE_TURN)` (Tier-2); both feed one retry gate.
  - *DoD:* illegal (either tier) → `ERROR{ILLEGAL_MOVE, reason}` + re-`MOVE_REQUEST` `attempt++` (FR-MO3, 7.d).
- [ ] **RE.3** Retry cap = `retry_cap` (default 1); on exhaustion record a penalized empty `TurnRecord` and continue.
  - *DoD:* retried structural fouls only; weak content scores low, never retried (FR-MO2, 3b).
- [ ] **RE.4** Broadcast `STATE_UPDATE{state, last_move, active_player}` after each turn; players read tell/flag off `state.transcript[-1]`.
  - *DoD:* no `referee_feedback` field added to the payload (FR-MO1, 7.b).
- [ ] **RE.5** Maintain the loop-private numeric trajectory; inject as `score_trajectory`, append each decision's `turn_scores`; dump to `results/` post-game only.
  - *DoD:* numbers never appear in any wire payload (6.d, 2a).
- [ ] **RE.6** Move-timeout = one per-turn wall-clock budget shared across retries (no reset on re-request); on expiry → penalized empty `TurnRecord` (`flag="timeout"`, floor scores), advance, continue.
  - *DoD:* a timed-out turn does not forfeit; match continues (FR-FT1, 8.1).
- [ ] **RE.7** Discriminate alive-but-silent (heartbeat flowing) → penalized skip & keep data; dead (beats stopped, watchdog fires) → disconnect.
  - *DoD:* raising `move_timeout` never trips a false disconnect (FR-FT2/FT3, 8.2).
- [ ] **RE.8** Mid-match disconnect → forced verdict on partial transcript, tag `terminated_reason="disconnect"`, mark for exclusion + same-seed re-run.
  - *DoD:* disconnect still emits exactly one `GAME_OVER` (FR-FT4, 8.3).
- [ ] **RE.9** Protocol-garbage split: bad content → `ERROR{MALFORMED_MESSAGE}` + drop frame (no turn advance); broken stream → escalate to disconnect.
  - *DoD:* repeated garbage until `move_timeout` → penalized skip (FR-FT5, 8.4).
- [ ] **RE.10** Wrap the post-`GAME_START` match in `try/finally` guaranteeing a `GAME_OVER` + trajectory dump even on unexpected exception (degenerate aborted verdict, tagged).
  - *DoD:* an injected exception still yields exactly one `GAME_OVER` (FR-FT7, 8.6, R-AC6).

## Module F — Config & constants (S7 + S8) → parent T1.2/T1.5

> Covers FR-CF1–FR-CF2, protocol mapping §10.

- [ ] **RF.1** Add the version-stamped `debate` block to `config/setup.json` with `format`/`judge`/`player`/`match` sub-groups and the defaults in PRD §9.
  - *DoD:* `shared/config.py` loads it; version `"1.00"`; no operational value in source (FR-CF1, AC8).
- [ ] **RF.2** Add `debate.player.ablation = {master, vectors{...}, baseline_mode}`; `master=false` ⇒ OFF roster, all-true ⇒ full ON.
  - *DoD:* both players read the identical block (FR-CF2, 7.j).
- [ ] **RF.3** Add `MALFORMED_MESSAGE` (and confirm `ILLEGAL_MOVE`) error-code tokens + the debate config-key names to `constants.py`.
  - *DoD:* no magic strings for codes/keys elsewhere (8.4, 7.d).
- [ ] **RF.4** Confirm AC9: no new `MessageType`, no payload field added, `PROTOCOL_VERSION` stays `"1.00"`.
  - *DoD:* `git diff` on `services/protocol/` is empty after the debate lands (R-AC9, 7.a).

## Module G — Integration gate (T6.3)

- [ ] **RG.1** Wire a **seeded/canned** Phase-1 player brain (parent T5.2) so word counts are reproducible.
  - *DoD:* not entropy-random; same seed ⇒ same utterances (FR-SB8, 9.h).
- [ ] **RG.2** Integration test: real referee + 2 players over localhost run the **real `DebateEngine`** + `SimpleRefereeBrain` through the full lifecycle to `GAME_OVER`.
  - *DoD:* AC3 reproducible; passes in CI; asserts exactly one verdict (R-AC5, 9.i).
- [ ] **RG.3** Assert byte-identical verdict across two runs at the same seed.
  - *DoD:* the determinism anchor holds (R-AC4, 8.6).

## Module H — Phase-7 LLM brain (S2/S6) → parent T7.2

- [ ] **RH.1** `LLMRefereeBrain(LLMCallerMixin, RefereeBrain)` honoring the same `decide()`; builds the judge prompt; tell + per-criterion scores in one call.
  - *DoD:* same interface as `SimpleRefereeBrain`; tested with a mocked `LLMCallerMixin` (FR-RB7, 6.f).
- [ ] **RH.2** `judge_variant` strategy switch: naive vs hardened prompt; Arm-3 runs `_verify_grounding(move, evidence_pack)` against the pack feeding the Evidence criterion.
  - *DoD:* verdict structure identical across the 3 arms (FR-JU6/JU7, 6.g).
- [ ] **RH.3** Confirm the swap touches **only** the brain classes — engine/state/config/protocol unchanged.
  - *DoD:* AC9 still holds end-to-end (RG-8, 9.i).

## Module I — Experiment harness (S8) → parent TC.8

- [ ] **RI.1** Thin sweep-runner: iterate condition cells (ablation master/vectors × `judge.variant` × seed mirror pairs) from the config block; no per-condition source edit.
  - *DoD:* ~250–400 matches run via config/CLI only (FR-EX1/EX2/EX6, AC8).
- [ ] **RI.2** Define the 3 `results/` JSONL streams (verdict+trajectory / private-capture / metadata) sharing keys `(match_id, seed, turn_number)`.
  - *DoD:* the streams join cleanly in the notebook (FR-EX4, 8.10).
- [ ] **RI.3** Analysis notebook: defense-strength curve (win-rate vs 3 arms), READ-accuracy partial correlation, position-bias flip-rate.
  - *DoD:* runs end-to-end; reports H1–H5 (FR-EX5/EX7, 8.11/8.15).
- [ ] **RI.4** Curate the per-motion evidence pack(s) (~10–20 real source-snippets) + the motion pool.
  - *DoD:* the locked primary motion (L2) has a fixed pack; deterministic across conditions (4f, 8.14).

---

## Build order (dependency-ordered)

`Module A → B → C → D → E → F → G (gate) → H → I`.
The gate is **RG.2**: when the real `DebateEngine` + `SimpleRefereeBrain` run to a
reproducible `GAME_OVER`, the substrate is proven game/brain-agnostic and the LLM phase
(Module H) becomes a dependency-injection swap.
