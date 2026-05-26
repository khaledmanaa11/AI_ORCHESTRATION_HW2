# Task Tracking — Referee & Debate Game

| Field    | Value                                       |
|----------|---------------------------------------------|
| Document | `TODO_referee.md`                           |
| Project  | `agent-arena`                               |
| Version  | 1.00                                        |
| Date     | 2026-05-25                                  |

---

## ⚡ NEXT-SESSION HANDOFF (pick up here)

**Completed so far:** Modules A → H (commits a4b4aaf → 761b4f4 + 0e9434a).
**Current gate result:** ruff=0 violations, 230/230 tests pass, coverage = **95.55%**.

**Start next session with Module I** — implement:

### Module I — LLM referee brain (Phase 7)
- Swap-in real LLM referee brain over same `decide()` interface.
- 3-arm judge variant strategies.
- Verify grounding/Evidence check under Arm-3.

**Build order reminder:** H (gate) → I → J. Commit after each module passes gate.

---

> Status: `[ ]` not started · `[~]` in progress · `[x]` done
> Every task maps to a requirement in [PRD_referee.md](PRD_referee.md) and a ledger decision
> in [DESIGN_LEDGER.md](DESIGN_LEDGER.md). Companion: [PLAN_referee.md](PLAN_referee.md).
> Aligns with parent [TODO.md](TODO.md) tasks (T4.1/4.3/4.4/4.5/4.6/4.7/4.8, T5.2, T6.3, T7.2, TC.8).
> **Cross-cutting rules (assert per module, Module K):** every source file ≤ 150 code lines,
> `ruff check` clean, coverage ≥ 85 %, no hardcoded operational values, no magic strings.
> **Commit cadence:** one commit per completed task-block (a lettered sub-section), only after
> its tests + `ruff` pass — see the build order at the bottom.
> **Completeness:** the [§ Coverage Matrix](#coverage-matrix--every-prd-requirement--task) at the
> end maps **every** PRD requirement ID to the task(s) that satisfy it.

---

## Module A — Game state & move · `services/game/debate_state.py` (S5) → T4.3  ✅ DONE (commit a4b4aaf)

### A1 — File setup
- [x] **RA1.1** Create `services/game/debate_state.py` with a module docstring + `from __future__ import annotations`, `from dataclasses import dataclass, field`, `from typing import Any`.
  - *DoD:* file exists; `ruff` clean; imports used.
- [x] **RA1.2** Add a module logger `logger = logging.getLogger(__name__)`.
  - *DoD:* logger name `"agent_arena.services.game.debate_state"`.

### A2 — `TurnRecord` (FR-ST4, FR-ST5)
- [x] **RA2.1** Define `@dataclass(frozen=True) class TurnRecord` with `turn_number:int, side:str, phase:str, utterance:str, word_count:int, retry_count:int, referee_tell:str|None, referee_flag:str|None`.
  - *DoD:* instances are immutable (assignment raises `FrozenInstanceError`).
- [x] **RA2.2** Add `TurnRecord.to_dict()` and `from_dict()`.
  - *DoD:* `from_dict(r.to_dict()) == r`.

### A3 — `DebateMove` (FR-ST7)
- [x] **RA3.1** Define `@dataclass(frozen=True) class DebateMove` with one field `text:str`.
  - *DoD:* no other public field exists.
- [x] **RA3.2** Add `to_dict()` → `{"text": self.text}` and `from_dict()`.
  - *DoD:* `DebateMove("x").to_dict() == {"text":"x"}`; round-trips (R-AC1).

### A4 — `DebateState` fields (FR-ST2, FR-ST8)
- [x] **RA4.1** Define `@dataclass(frozen=True) class DebateState` with `motion:str, turn_number:int=0, transcript:tuple[TurnRecord,...]=(), status:str="PENDING", verdict:dict|None=None, rules_snapshot:dict=field(default_factory=dict)` (rules_snapshot = `{R, word_cap, retry_cap, total_turns}`).
  - *DoD:* fields exactly match FR-ST2; `verdict=None` until terminal.
- [x] **RA4.2** Assert (by construction + a test) that `DebateState` holds **no** rubric, weights, evidence_pack, or numeric trajectory — only `motion` is contextual (FR-ST8).
  - *DoD:* a test asserts those keys never appear on the instance or in `to_dict()`.

### A5 — Derived schedule helpers (FR-ST3)
- [x] **RA5.1** Implement `total_turns(R)` → `2 + 2*R + 2`.
  - *DoD:* `total_turns(3) == 10`.
- [x] **RA5.2** Implement `active_side(turn_number)` → `"PRO"` if odd else `"CON"` (no stored side).
  - *DoD:* turns 1/3/5/7/9 → PRO; 2/4/6/8/10 → CON (1b).
- [x] **RA5.3** Implement `phase(turn_number)` → OPENING (1–2), REBUTTAL (next 2R), CLOSING (last 2); and `rebuttal_round(turn_number)` → `⌈(t−2)/2⌉` within rebuttal.
  - *DoD:* schedule matches 5.4d for R=3.
- [x] **RA5.4** Make `first_speaker` configurable so PRO/CON-first flips for mirror pairs (1b/8.8) — the schedule derives `active_side` relative to `first_speaker`.
  - *DoD:* flipping `first_speaker` swaps the per-turn side mapping deterministically.

### A6 — Serialization (FR-ST1, FR-ST6)
- [x] **RA6.1** Implement `DebateState.to_dict()` carrying public-only fields: `motion, turn_number, derived phase+active_side, transcript (list of TurnRecord.to_dict), status, verdict (if terminal), rules_snapshot`.
  - *DoD:* no private reasoning, no numeric trajectory present (FR-ST6, R-AC2).
- [x] **RA6.2** Implement `DebateState.from_dict()` as the lossless inverse.
  - *DoD:* `from_dict(s.to_dict()) == s` for pre-start, mid-match, and terminal states (R-AC1).

### A7 — Tests
- [x] **RA7.1** `tests/unit/services/game/test_debate_state.py`: round-trip for `TurnRecord`/`DebateMove`/`DebateState`.
  - *DoD:* pytest collects; all round-trips pass.
- [x] **RA7.2** Test the derived schedule (side/phase/round) across all 10 turns at R=3 and one non-default R.
  - *DoD:* assertions pass for both R values.
- [x] **RA7.3** Test the **public-only invariant**: `to_dict()` contains none of `{scores, trajectory, rubric, weights, evidence_pack, reasoning}` (R-AC2, FR-ST6/ST8).
  - *DoD:* assertion passes; this is the AC2 guard.
- [x] **RA7.4** Test immutability: assigning to any field raises.
  - *DoD:* `pytest.raises(FrozenInstanceError)`.

---

## Module B — Game engine · `services/game/debate_engine.py` (S5) → T4.1/T4.2  ✅ DONE (commit 557cfe5)

### B1 — Class skeleton (FR-EN7)
- [x] **RB1.1** Create the file; define `class DebateEngine(GameEngine)` with a docstring "pure deterministic debate mechanics; no LLM/network/disk".
  - *DoD:* importable; subclasses the existing `GameEngine` ABC.
- [x] **RB1.2** Constructor takes `rules` (R, word_cap, retry_cap, first_speaker, motion) — no I/O, no globals.
  - *DoD:* `DebateEngine` holds only config-derived rules; no socket/LLM import (FR-EN7, R-AC3-adjacent).

### B2 — Initial state (FR-EN6)
- [x] **RB2.1** `get_initial_state()` → `DebateState(motion, turn_number=0, status="PENDING", transcript=(), rules_snapshot=…)`.
  - *DoD:* matches GAME_START.initial_state shape (7.h).

### B3 — Tier-1 mechanical validation (FR-EN4)
- [x] **RB3.1** `validate_move(state, move)` rejects empty/whitespace `text` → reason token `"empty"`.
  - *DoD:* returns illegal+`"empty"` for `""`/`"   "`.
- [x] **RB3.2** Reject over-length (`word_count(text) > word_cap`) → `"over_length"`.
  - *DoD:* a 251-word move at cap 250 is illegal.
- [x] **RB3.3** Reject malformed (missing/non-str `text`) → `"malformed"`.
  - *DoD:* `{"text": 5}` and `{}` are illegal.
- [x] **RB3.4** A valid in-cap move passes Tier-1.
  - *DoD:* legal=True; reason None.
- [x] **RB3.5** Define `word_count(text)` once (whitespace split) and reuse everywhere (no duplicate counting logic).
  - *DoD:* single source of truth for word counting.

### B4 — Legal-move descriptor (FR-EN5)
- [x] **RB4.1** `get_legal_moves(state)` → one-element list `[{type:"utterance", turn_number, side, phase, word_cap, must_engage, attempt, max_attempts}]`.
  - *DoD:* `list[Any]` length 1; `must_engage` True in REBUTTAL/CLOSING, False in OPENING (1d).

### B5 — Apply move & penalized turns (FR-EN1, FR-EN3)
- [x] **RB5.1** `apply_move(state, move, *, tell=None, flag=None, retry_count=0)` → fresh frozen `DebateState` with a new `TurnRecord` appended; never mutates input.
  - *DoD:* input unchanged; `turn_number` += 1; transcript grows by one.
- [x] **RB5.2** Support appending a **penalized empty** `TurnRecord` (`utterance=""`, `word_count=0`, `flag` in {`"timeout"`,`"retry_exhausted"`}) that still advances the counter.
  - *DoD:* an empty penalized turn advances `turn_number` (FR-EN3, 8.1).

### B6 — Terminal detection (FR-EN2)
- [x] **RB6.1** `is_terminal(state)` → True iff `turn_number == total_turns` and all turns recorded; sets/derives `status="COMPLETE"`.
  - *DoD:* terminal exactly at the last scheduled turn, not before.

### B7 — Tests
- [x] **RB7.1** `test_debate_engine.py`: drive a full 10-turn schedule via `apply_move`; assert terminal at turn 10.
  - *DoD:* loop reaches `is_terminal()`.
- [x] **RB7.2** Test each Tier-1 rejection (empty/over_length/malformed) returns the right token.
  - *DoD:* three assertions pass.
- [x] **RB7.3** Test immutability of `apply_move` (input state object identity unchanged, fields equal).
  - *DoD:* assertion passes.
- [x] **RB7.4** Test the penalized-empty-turn path advances the counter.
  - *DoD:* assertion passes (8.1 wiring precondition).

---

## Module C — Referee brain contract · `services/referee/brain/base.py` (S6) → T4.7  ✅ DONE (commit 4703095)

### C1 — Request kind & dataclasses (FR-RB2, FR-RB3, FR-RB4)
- [x] **RC1.1** Define `class RequestKind(StrEnum)` = `EVALUATE_TURN`, `RENDER_VERDICT`.
  - *DoD:* no string literals for kinds elsewhere (6.a).
- [x] **RC1.2** Define `@dataclass class RefereeContext` = `{request_kind, state:dict, move:dict|None, rubric:dict, judge_variant:str, evidence_pack:dict, score_trajectory:list}`.
  - *DoD:* `move=None` valid; fields match FR-RB3.
- [x] **RC1.3** Define `@dataclass class RefereeDecision` = `{legal:bool=True, flag:str|None=None, tell:str|None=None, turn_scores:dict|None=None, verdict:dict|None=None}`.
  - *DoD:* one dataclass serves both kinds (FR-RB4, 6.c).

### C2 — Abstract brain (FR-RB1, FR-RB5, FR-RB7)
- [x] **RC2.1** Define `class RefereeBrain(ABC)` with `@abstractmethod def decide(self, context: RefereeContext) -> RefereeDecision`.
  - *DoD:* cannot instantiate the ABC; subclass with `decide` can (FR-RB1).
- [x] **RC2.2** Docstring states: stateless pure function; two-kind dispatch; trajectory injected by the loop; **no LLM-only fields** in Context/Decision (FR-RB5, FR-RB7).
  - *DoD:* interface documented; no prompt/token/temperature field exists (6.i).

### C3 — Shared deterministic verdict aggregate (FR-JU5, 6.h) — reused by both brains
- [x] **RC3.1** Implement a pure helper `aggregate_verdict(trajectory, weights, tiebreak_fn) -> dict` returning the 2e shape `{winner, margin, scores:{PRO,CON per-criterion}, weighted_totals, rationale}`; per-criterion final = mean of that side's per-turn scores → weighted.
  - *DoD:* deterministic; same trajectory → same dict (REF-007).
- [x] **RC3.2** The helper is **total**: all-zero/partial trajectories yield a valid verdict, never raises; tie resolved by the injected `tiebreak_fn`.
  - *DoD:* empty/all-zero trajectory returns a well-formed verdict (FR-SB6, 8.6).

### C4 — Tests
- [x] **RC4.1** `test_brain_base.py`: ABC cannot be instantiated; a trivial subclass works.
  - *DoD:* assertions pass.
- [x] **RC4.2** Test `aggregate_verdict` on a hand-computed trajectory (known means → known winner/margin).
  - *DoD:* matches the hand calculation exactly.
- [x] **RC4.3** Test the total/never-raises property on all-zero and single-turn trajectories.
  - *DoD:* no exception; valid 2e shape.

---

## Module D — `SimpleRefereeBrain` · `services/referee/brain/simple_brain.py` (S9) → T4.8  ✅ DONE (commit 12f5004)

### D1 — Class & dispatch (FR-SB1)
- [x] **RD1.1** Define `class SimpleRefereeBrain(RefereeBrain)`; `decide` dispatches on `context.request_kind`.
  - *DoD:* **no** import of LLM/socket/`random`/`time`/file I/O (FR-SB1, R-AC3).
- [x] **RD1.2** Add a CI/grep guard test asserting the module imports none of `{anthropic, socket, random, time, open}`.
  - *DoD:* the guard test passes (R-AC3 enforcement).

### D2 — EVALUATE_TURN legality (FR-SB2)
- [x] **RD2.1** Define a module-level frozen `CONCESSION_TOKENS` set (e.g. `"i concede"`, `"i give up"`, `"you win"`, `"i forfeit"`).
  - *DoD:* tokens defined once (no magic strings).
- [x] **RD2.2** Scan the case-folded utterance for any token → `legal=False, flag="concession"`; else `legal=True`. Off-topic never flagged.
  - *DoD:* concession utterance illegal; normal legal (FR-SB2, 9.b).

### D3 — Tell (FR-SB3)
- [x] **RD3.1** Build a number-free `tell` from public turn data only, e.g. `f"[T{n} {side}/{phase}] acknowledged — {wc} words."`
  - *DoD:* tell contains no numeric score; no coaching (FR-SB3, 9.c).

### D4 — Scores (FR-SB4)
- [x] **RD4.1** Compute `s = round(min(word_count/word_cap, 1.0)*10, 2)`; emit `turn_scores = {logic:s, evidence:s, rebuttal:s, persuasion:s}`.
  - *DoD:* identical across the 4 criteria; pure function (FR-SB4, 9.d).
- [x] **RD4.2** `word_count==0` → all scores `0.0` (coincides with the penalized-skip floor).
  - *DoD:* assertion passes (8.1 alignment).

### D5 — RENDER_VERDICT (FR-SB5, FR-SB6)
- [x] **RD5.1** Define the deterministic tiebreak `simple_tiebreak(trajectory)` = greater cumulative `word_count`; still tied → `first_speaker` (PRO).
  - *DoD:* tie resolves deterministically (FR-SB5, 9.e).
- [x] **RD5.2** RENDER_VERDICT calls `aggregate_verdict(trajectory, weights, simple_tiebreak)` (RC3.1) and templates the `rationale`.
  - *DoD:* output is the full 2e shape (R-AC7).

### D6 — Variant/pack ignored (FR-SB7)
- [x] **RD6.1** Read neither `judge_variant` nor `evidence_pack`; no `_verify_grounding`.
  - *DoD:* identical output across all `judge_variant` values (FR-SB7, 9.g).

### D7 — Tests
- [x] **RD7.1** Determinism: call `decide` twice with the same context → equal decisions (R-AC4).
  - *DoD:* assertion passes.
- [x] **RD7.2** Concession path; normal path; word-count scoring; wc=0 floor.
  - *DoD:* four assertions pass.
- [x] **RD7.3** Total verdict over an all-zero trajectory; variant-invariance across naive/hardened/structural.
  - *DoD:* assertions pass (FR-SB6/SB7).

---

## Module E — Game loop & fault policy · `services/referee/game_loop.py` + `_turn_runner.py` + `result.py` (S3, S8) → T4.5/T4.6  ✅ DONE (commit bc00e69)

> **Implementation note:** `game_loop.py` was split into three files to stay ≤150 lines:
> `_turn_runner.py` (per-turn recv/retry/fault logic), `game_loop.py` (orchestrator), `result.py` (trajectory dump).

### E1 — Turn issue (FR-MO?, 5.7e)
- [x] **RE1.1** Derive `active_side` from `turn_number`+`first_speaker`; send `MOVE_REQUEST{state, legal_moves, move_timeout_seconds}` to the **active player only**, echoing `side`+`turn_number`.
  - *DoD:* broadcast never used for MOVE_REQUEST (5.7e).

### E2 — Two-tier legality + retry gate (FR-MO2, FR-MO3, FR-MO4, FR-RB2, FR-RB6)
- [x] **RE2.1** On a received move: run `engine.validate_move` (Tier-1); if illegal → retry gate with the reason token.
  - *DoD:* Tier-1 fail does not call the brain.
- [x] **RE2.2** If Tier-1 passes, call `brain.decide(EVALUATE_TURN, …)` once (Tier-2 + tell + scores in one call).
  - *DoD:* exactly one brain call per attempt (FR-RB6, 6.f).
- [x] **RE2.3** Assert **no pre-turn brain call** is ever issued (only EVALUATE_TURN / RENDER_VERDICT).
  - *DoD:* a test counts brain calls = (#turns scored) + 1 verdict (FR-RB2, 6.a).
- [x] **RE2.4** On illegal (either tier): send `ERROR{code="ILLEGAL_MOVE", message=reason}` to the active player, then re-issue `MOVE_REQUEST` with `attempt+1`.
  - *DoD:* ERROR is active-player-only, not broadcast (7.d).
- [x] **RE2.5** Retry cap = `retry_cap` (default 1, config); structural fouls only — weak content (legal but low score) is never retried.
  - *DoD:* a legal weak move is scored, not retried (FR-MO2, 3b).
- [x] **RE2.6** On retry exhaustion: append a penalized empty `TurnRecord` (`flag="retry_exhausted"`) via `apply_move`; match continues.
  - *DoD:* counter advances; loop continues (FR-MO3).

### E3 — Broadcast & trajectory (FR-MO1, FR-JU1, FR-RB5)
- [x] **RE3.1** After a recorded turn, broadcast `STATE_UPDATE{state, last_move, active_player}`; players read tell/flag off `state.transcript[-1]`.
  - *DoD:* **no** `referee_feedback` field added to the payload (FR-MO1/JU1, 7.b).
- [x] **RE3.2** Maintain the loop-private numeric trajectory; inject as `score_trajectory` each `decide`; append each decision's `turn_scores`.
  - *DoD:* trajectory never appears in any wire payload (FR-RB5, 2a).

### E4 — Terminal & verdict (FR-FT7, FR-JU5)
- [x] **RE4.1** On `engine.is_terminal()`, call `brain.decide(RENDER_VERDICT, score_trajectory=…)`.
  - *DoD:* fires exactly once at terminal (6.a).
- [x] **RE4.2** `result.py`: emit `GAME_OVER{result=winner, reason=rationale, final_state=DebateState.to_dict() with verdict}` and dump the trajectory to `results/` post-game.
  - *DoD:* full 2e verdict on the wire (7.c, R-AC7); numbers only in the post-game dump (6.d).

### E5 — Move-timeout policy (FR-FT1, FR-FT2, FR-FT3)
- [x] **RE5.1** Start one per-turn wall-clock budget (`move_timeout_seconds`) at `MOVE_REQUEST`; the clock does **not** reset on a 3b re-request (shared across retries).
  - *DoD:* total per-turn wall-clock ≤ `move_timeout` regardless of attempts (FR-FT1, 8.1).
- [x] **RE5.2** On expiry: append a penalized empty `TurnRecord` (`flag="timeout"`, floor scores), advance, continue — never forfeit.
  - *DoD:* timed-out turn yields a scored-zero turn, match continues.
- [ ] **RE5.3** Use the existing `WatchdogThread`/`HeartbeatSender` for liveness, decoupled from `move_timeout`; raising `move_timeout` must not trip a disconnect.
  - *DoD:* a slow-but-beating peer is not disconnected (FR-FT2/FT3, 8.2).
  - **NOTE:** `recv_timed` handles the move timeout; WatchdogThread integration deferred to the TCP server wiring (Module F/H).
- [ ] **RE5.4** Discriminator: beats flowing + no move → penalized skip (keep data); beats stopped → disconnect path (RE6).
  - *DoD:* the two paths are distinguished by heartbeat state (8.2).
  - **NOTE:** deferred to server wiring (Module F/H); in-memory tests use `ConnectionClosedError` directly.

### E6 — Disconnect & garbage (FR-FT4, FR-FT5)
- [x] **RE6.1** On `ConnectionClosedError` after GAME_START: terminate with a forced verdict on the partial transcript; tag `terminated_reason="disconnect"`.
  - *DoD:* still emits exactly one `GAME_OVER` (FR-FT4, 8.3).
- [x] **RE6.2** Tag disconnect matches for **exclusion** from aggregates + same-seed re-run (metadata flag, consumed by the sweep runner).
  - *DoD:* the GAME_OVER payload carries `terminated_reason="disconnect"` (8.3).
- [x] **RE6.3** Bad **content** (codec/validation error): reply `ERROR{code="MALFORMED_MESSAGE", message=reason}`, drop the frame, do **not** advance the turn (the move_timeout still governs).
  - *DoD:* repeated garbage until expiry → penalized skip (FR-FT5, 8.4).
- [x] **RE6.4** Broken **stream** (`ConnectionClosedError`/`FrameTooLargeError`): escalate to the disconnect path (RE6.1).
  - *DoD:* a closed/oversized stream → disconnect, not MALFORMED (8.4).

### E7 — The invariant (FR-FT7)
- [x] **RE7.1** Wrap the post-`GAME_START` match in `try/finally` guaranteeing a `GAME_OVER` + trajectory dump even on an unexpected exception (degenerate "aborted" verdict, tagged `terminated_reason="aborted"`).
  - *DoD:* an injected mid-loop exception still yields exactly one `GAME_OVER` (FR-FT7, 8.6, R-AC6).

### E8 — Tests
- [x] **RE8.1** Loop happy path with `SimpleRefereeBrain` + stub channels → exactly one `GAME_OVER`.
  - *DoD:* assertion passes.
- [x] **RE8.2** Retry gate: illegal then legal resubmit; retry exhaustion → penalized turn.
  - *DoD:* both paths covered.
- [x] **RE8.3** Move-timeout → penalized skip (no forfeit); shared budget across retries.
  - *DoD:* assertions pass (8.1). Implemented via `unittest.mock.patch` on `recv_timed`.
- [x] **RE8.4** Disconnect → forced verdict tagged; MALFORMED content drop vs broken-stream disconnect.
  - *DoD:* three assertions pass (8.3/8.4).
- [x] **RE8.5** Injected exception under `try/finally` still yields one `GAME_OVER` (the 8.6 guard).
  - *DoD:* assertion passes (R-AC6).
- [x] **RE8.6** Brain-call count test (no pre-turn call) — RE2.3.
  - *DoD:* count == scored-turns + 1.

---

## Module F — Match setup & protocol mapping · `services/referee/matchmaking.py` (debate bits) + `result.py` (S7, S8) → T4.4  ✅ DONE (commit de73d5c)

> Covers Protocol-Mapping §10 rows and the pre-`GAME_START` abort (FR-FT6). **No protocol code edits.**

### F1 — `game_config` assembly (Protocol §10: ROLE_ASSIGN.game_config; 7.f/7.g)
- [x] **RF1.1** Build `game_config = {motion, rubric:{criteria, weights}, tie_break, verdict_structure, conduct_gate, format:{total_turns, R, word_cap, first_speaker, phase_schedule}, evidence_pack}`.
  - *DoD:* contents match 7.g exactly.
- [x] **RF1.2** **Exclude** `judge_variant` from `game_config` (referee-private).
  - *DoD:* a test asserts `"judge_variant"` is absent from any player-bound payload (7.g, R-AC2-adjacent).
- [x] **RF1.3** The **identical** evidence pack is sent to both players (symmetry, L4).
  - *DoD:* both ROLE_ASSIGN payloads carry the same pack bytes.

### F2 — Seeded side assignment & ROLE_ASSIGN (1e; Protocol §10: ROLE_ASSIGN.role)
- [x] **RF2.1** Assign PRO/CON by seedable RNG (config `seed`); side hidden until match start.
  - *DoD:* same seed → same assignment; reproducible (1e).
- [x] **RF2.2** Send each player its own `ROLE_ASSIGN{role=side, game_config}` (REGISTER_ACK with match_id first, then ROLE_ASSIGN — parent T4.4 sequencing).
  - *DoD:* role carries the side; game_config carries the pack+rubric (7.f).

### F3 — GAME_START construction (Protocol §10: GAME_START; 7.h)
- [x] **RF3.1** Build `GAME_START{initial_state=DebateState.to_dict() @ turn 0, turn_order=[first,second]}` where `first` follows `first_speaker`.
  - *DoD:* initial_state status PENDING, empty transcript; turn_order respects first_speaker (7.h).

### F4 — Pre-`GAME_START` abort (FR-FT6, 8.5)
- [x] **RF4.1** If the 2nd player never registers, a 3rd connects, or a player drops during lobby → `lobby_timeout_seconds` fires → clean abort, **no verdict, no data cell**.
  - *DoD:* aborted match writes **no** results row (distinct from the disconnect case, 8.3).
- [x] **RF4.2** Reuse existing matchmaking reject-3rd + lobby_timeout logic — no new mechanism.
  - *DoD:* no new infra added (8.5).

### F5 — Tests
- [x] **RF5.1** `game_config` shape test incl. the `judge_variant`-absent assertion (RF1.2).
  - *DoD:* assertion passes (the AC9/secrecy guard).
- [x] **RF5.2** Seeded side-assignment reproducibility test.
  - *DoD:* same seed → same side mapping.
- [x] **RF5.3** Pre-start abort writes no data cell; mid-match disconnect (RE6) does write a tagged row — assert the boundary.
  - *DoD:* the 8.5↔8.3 boundary is tested.

---

## Module G — Config & constants · `config/setup.json` + `constants.py` (S7) → T1.2/T1.5

### G1 — `debate` config block (FR-CF1, FR-CF2)
- [x] **RG1.1** Add `debate.format` = `{rebuttal_rounds:3, word_cap:250, first_speaker:"PRO", retry_cap:1}` (total_turns derived, not stored).
  - *DoD:* `shared/config.py` loads it; version `"1.00"` (FR-CF1, 7.i).
- [x] **RG1.2** Add `debate.judge` = `{variant:"naive", weights:{logic:30,evidence:30,rebuttal:25,persuasion:15}}` (referee-only).
  - *DoD:* loaded; weights sum to 100 (validation).
- [x] **RG1.3** Add `debate.player` = `{best_of_N:3, private_capture:true, ablation:{master:false, vectors:{sycophancy,authority,bandwagon,fallacy,adaptive_persona,bestN_judge_select,read_targeting}, baseline_mode:"beta"}}`.
  - *DoD:* `master=false` ⇒ OFF roster; both players read identical block (FR-CF2, 7.j).
- [x] **RG1.4** Add `debate.match` = `{motion:"<id>", evidence_pack:"<id>", seed:<int>}`.
  - *DoD:* loaded; referee selects, motion+pack flow to players (7.i).
- [x] **RG1.5** Extend `shared/config.py` validation for the `debate` block (types, weight sum, variant enum).
  - *DoD:* a malformed block raises a typed error (no operational value in source, AC8).

### G2 — Constants (7.d, 8.4)
- [x] **RG2.1** Add error-code tokens `ERROR_ILLEGAL_MOVE="ILLEGAL_MOVE"`, `ERROR_MALFORMED_MESSAGE="MALFORMED_MESSAGE"` and reason tokens (`empty`/`over_length`/`malformed`/`off_topic`/`concession`/`timeout`/`retry_exhausted`).
  - *DoD:* no magic strings for codes/reasons elsewhere (7.d, 8.4).
- [x] **RG2.2** Add `terminated_reason` tokens (`disconnect`/`aborted`) and debate config-key name constants.
  - *DoD:* loop + result use the constants, not literals.

### G3 — Tests
- [x] **RG3.1** `test_config` extension: load the debate block, assert defaults + validation failures.
  - *DoD:* assertions pass.

---

## Module H — Integration gate (T6.3) → the hard gate

### H1 — Seeded placeholder player (FR-SB8, T5.2)
- [x] **RH1.1** Implement/parameterize a **seeded or canned** Phase-1 player brain (fixed-seed utterances), not entropy-random.
  - *DoD:* same seed ⇒ identical utterances run-to-run (FR-SB8, 9.h).

### H2 — End-to-end test (R-AC5, R-AC4, R-AC6)
- [x] **RH2.1** `tests/integration/test_debate_loop.py`: real referee + 2 players over localhost run the **real `DebateEngine`** + `SimpleRefereeBrain` through `REGISTER→…→GAME_OVER`.
  - *DoD:* AC3 reproducible; one verdict; passes in CI (R-AC5, 9.i).
- [x] **RH2.2** Run the match twice at the same seed; assert byte-identical `final_state.verdict`.
  - *DoD:* determinism anchor holds (R-AC4).
- [x] **RH2.3** Fault-injection integration: kill a player mid-match → tagged forced verdict; timeout a turn → penalized skip.
  - *DoD:* each still reaches exactly one `GAME_OVER` (R-AC6, 8.6).

---

## Module I — LLM referee brain (Phase 7) · `services/referee/brain/llm_brain.py` (S2, S6) → T7.2  ✅ DONE

> Same `decide()` interface; **swap-only** (engine/state/config/protocol unchanged). Covers FR-JU1–JU7.

### I1 — Class & call (FR-RB7, FR-JU2, FR-JU5)
- [x] **RI1.1** `class LLMRefereeBrain(LLMCallerMixin, RefereeBrain)`; `decide` dispatches on `request_kind`.
  - *DoD:* same interface as `SimpleRefereeBrain`; mocked `LLMCallerMixin` in unit tests (no real API).
- [x] **RI1.2** EVALUATE_TURN: one LLM call produces **both** the public `tell` and private per-criterion `turn_scores` (Logic/Evidence/Rebuttal/Persuasion, 0–10).
  - *DoD:* one invocation; tell number-free; scores cover the 4 criteria (FR-JU1/JU2, 6.f).
- [x] **RI1.3** RENDER_VERDICT reuses `aggregate_verdict` (RC3.1) with weights from config + an LLM-written holistic rationale; tiebreak = forced holistic call.
  - *DoD:* verdict is the full 2e shape; no draws (FR-JU4/JU5, 2d).

### I2 — Variant strategy (FR-JU3, FR-JU6, FR-JU7)
- [x] **RI2.1** `judge_variant` selects the judge prompt: naive (rubric straight) vs hardened (bias warnings, discount unverifiable, lean on checkable substance).
  - *DoD:* the three arms share rubric/weights/verdict, differ only in prompt (FR-JU6).
- [x] **RI2.2** Arm-3 only: run `_verify_grounding(move, evidence_pack)` (citations traceable to the pack) feeding the Evidence criterion; Arm-1/2 skip it.
  - *DoD:* fabricated/un-pack citations are caught only under Arm-3 (FR-JU7, 6.g).
- [x] **RI2.3** Apply config weights 30/30/25/15 in the aggregate (FR-JU3).
  - *DoD:* changing config weights changes the verdict deterministically (given fixed scores).

### I3 — Tests & swap proof
- [x] **RI3.1** Unit tests with mocked `LLMCallerMixin`: tell/scores parsing, 3-arm prompt selection, Arm-3 grounding.
  - *DoD:* no real API call; assertions pass.
- [x] **RI3.2** Re-run the integration gate (H2) swapping only the brain class → still one `GAME_OVER`, protocol unchanged.
  - *DoD:* AC9 holds end-to-end (RG-8, 9.i, R-AC9).

---

## Module J — Experiment harness (S8) → TC.8

### J1 — Evidence pack & motion (4f, 8.14)
- [ ] **RJ1.1** Curate the locked primary motion (L2) + its fixed evidence pack (~10–20 real source-snippets, mixed, serving both sides) in `data/`.
  - *DoD:* deterministic across conditions; same pack to both players (4f).
- [ ] **RJ1.2** (Optional) 1–2 additional motions + packs for external validity (8.14).
  - *DoD:* pool loads by `motion`/`evidence_pack` id.

### J2 — Sweep runner (FR-EX1, FR-EX2, FR-EX3, FR-EX6)
- [ ] **RJ2.1** Thin runner iterating cells: ablation `master` ON/OFF × `judge.variant` ∈ {naive,hardened,structural} × K seed-locked mirror pairs (default K=10) — all from the config block, **no per-condition source edit**.
  - *DoD:* a cell change is config/CLI only (R-AC10, 8.13).
- [ ] **RJ2.2** Mirror pair: for each seed run the paired match with `first_speaker` flipped + ON/OFF swapped; average win-rate over the pair.
  - *DoD:* position bias nets out in the headline (FR-EX2, 8.8).
- [ ] **RJ2.3** Per-vector teardown mode: one-at-a-time-ON from the OFF baseline vs the naive judge; secondary leave-one-out from full-ON.
  - *DoD:* the runner emits a labeled cell per vector (FR-EX3, 8.9).

### J3 — Results streams (FR-EX4)
- [ ] **RJ3.1** Define 3 `results/` JSONL streams sharing keys `(match_id, seed, turn_number)`: (a) verdict+trajectory, (b) player private-capture, (c) match metadata (condition cell, mirror-pair id, first_speaker, terminated_reason, motion/pack ids).
  - *DoD:* the streams join cleanly (FR-EX4, 8.10).

### J4 — Analysis notebook (FR-EX5, FR-EX7)
- [ ] **RJ4.1** `notebooks/` analysis: defense-strength curve (win-rate vs 3 arms).
  - *DoD:* renders the curve (FR-EX1).
- [ ] **RJ4.2** READ-accuracy partial correlation with win/margin controlling for tool-use count.
  - *DoD:* computes the centerpiece "reading > spamming" statistic (FR-EX5, 8.11).
- [ ] **RJ4.3** Position-bias flip-rate (vs the 44.8% anchor) + report H1–H5.
  - *DoD:* each hypothesis is checkable from the logs (FR-EX7, 8.15).

---

## Module K — Cross-cutting quality gates (every module) → TC.1/TC.2/TC.3/TC.4, R-AC11, R-AC9

- [x] **RK.1** After each module: `ruff check` reports 0 violations on the new files.
  - *DoD:* clean (TC.2, R-AC11). ✅ Verified for Modules A–E.
- [x] **RK.2** Every new source file ≤ 150 code lines; split when approaching the limit.
  - *DoD:* `wc -l` per file ≤ 150 (TC.3, R-AC11). ✅ `game_loop.py` split into 3 files.
- [x] **RK.3** Global coverage ≥ 85 % after each phase (`uv run pytest --cov`).
  - *DoD:* report ≥ 85 % (TC.1, R-AC11). ✅ 96% after Module E.
- [x] **RK.4** No hardcoded host/port/timeout/weight/cap in source — all from config.
  - *DoD:* grep finds no operational literals (TC.4, AC8). ✅ Verified for Modules A–E.
- [ ] **RK.5** **AC9 guard:** after the debate lands, `git diff` on `services/protocol/` is empty and `PROTOCOL_VERSION == "1.00"`.
  - *DoD:* zero protocol diff confirmed (R-AC9, 7.a) — assert in CI. ⏳ Verify at Module H.

---

## Build order (dependency-ordered; one commit per task-block)

`A → B → C → D → E → F → G → H (GATE) → I → J`, with **K asserted after every module**.

| Step | Block | Commit scope (suggested)        | Gate | Status |
|------|-------|----------------------------------|------|--------|
| 1 | A1–A7 | `feat(game/state)`               | round-trip + public-only tests green | ✅ a4b4aaf |
| 2 | B1–B7 | `feat(game/engine)`              | full schedule + Tier-1 tests green | ✅ 557cfe5 |
| 3 | C1–C4 | `feat(referee/brain-base)`       | ABC + aggregate tests green | ✅ 4703095 |
| 4 | D1–D7 | `feat(referee/simple-brain)`     | determinism + no-external-call guard green | ✅ 12f5004 |
| 5 | E1–E8 | `feat(referee/game-loop)`        | retry/timeout/disconnect/invariant tests green | ✅ bc00e69 |
| 6 | F1–F5 | `feat(referee/match-setup)`      | game_config + pre-start abort tests green | ✅ de73d5c |
| 7 | G1–G3 | `feat(config/debate)`            | config load + validation green | ✅ 761b4f4 |
| 8 | H1–H2 | `test(integration/debate-loop)`  | **HARD GATE — real DebateEngine → reproducible GAME_OVER** | ✅ 0e9434a |
| 9 | I1–I3 | `feat(referee/llm-brain)`        | swap-only; AC9 still holds | ⏳ |
| 10| J1–J4 | `feat(experiment/harness)`       | sweep + notebook run end-to-end | ⏳ |

The hard gate is **step 8 (H2)**: when the real `DebateEngine` + `SimpleRefereeBrain` run to a
reproducible `GAME_OVER`, the substrate is proven game/brain-agnostic and the LLM phase (Module I)
becomes a dependency-injection swap.

---

## <a name="coverage-matrix--every-prd-requirement--task"></a>Coverage Matrix — every PRD requirement → task(s)

> Critical completeness check: **no PRD requirement is unmapped.**

| PRD ID  | Covered by | PRD ID  | Covered by |
|---------|------------|---------|------------|
| RG-1    | RK.5, F1   | FR-RB1  | RC2.1      |
| RG-2    | RA*, A6    | FR-RB2  | RE2.3      |
| RG-3    | RC2.*      | FR-RB3  | RC1.2      |
| RG-4    | D*, H2     | FR-RB4  | RC1.3      |
| RG-5    | RE7.1, RE8.5 | FR-RB5 | RE3.2, RC2.2 |
| RG-6    | I1–I2, RC3 | FR-RB6  | RE2.2      |
| RG-7    | RJ2.1, G1  | FR-RB7  | RC2.2, RI1.1 |
| RG-8    | RI3.2, RK.5| FR-JU1  | RE3.1, RI1.2 |
| R-AC1   | RA2.2, RA3.2, RA6.2, RA7.1 | FR-JU2 | RI1.2, RD4.1 |
| R-AC2   | RA6.1, RA7.3, RF1.2 | FR-JU3 | RI2.3, RG1.2 |
| R-AC3   | RD1.1, RD1.2 | FR-JU4 | RI1.3, RD5.1 |
| R-AC4   | RD7.1, RH2.2 | FR-JU5 | RC3.1, RD5.2, RI1.3 |
| R-AC5   | RH2.1      | FR-JU6  | RI2.1      |
| R-AC6   | RE7.1, RE8.5, RH2.3 | FR-JU7 | RI2.2      |
| R-AC7   | RD5.2, RE4.2 | FR-MO1 | RE3.1      |
| R-AC9   | RK.5, RI3.2 | FR-MO2  | RE2.5      |
| R-AC10  | RJ2.1      | FR-MO3  | RE2.4, RE2.6 |
| R-AC11  | RK.1–RK.3  | FR-MO4  | RE2.1, RE2.2 |
| FR-ST1  | RA1, RA6   | FR-SB1  | RD1.1, RD1.2 |
| FR-ST2  | RA4.1      | FR-SB2  | RD2.1, RD2.2 |
| FR-ST3  | RA5.*      | FR-SB3  | RD3.1      |
| FR-ST4  | RA2.1      | FR-SB4  | RD4.1, RD4.2 |
| FR-ST5  | RA2.1, RE3.1 | FR-SB5 | RD5.1, RD5.2 |
| FR-ST6  | RA6.1, RA7.3 | FR-SB6 | RC3.2, RD7.3 |
| FR-ST7  | RA3.*      | FR-SB7  | RD6.1, RD7.3 |
| FR-ST8  | RA4.2, RA7.3 | FR-SB8 | RH1.1      |
| FR-EN1  | RB5.1      | FR-FT1  | RE5.1, RE5.2 |
| FR-EN2  | RB6.1      | FR-FT2  | RE5.3      |
| FR-EN3  | RB5.2      | FR-FT3  | RE5.4      |
| FR-EN4  | RB3.*      | FR-FT4  | RE6.1, RE6.2 |
| FR-EN5  | RB4.1      | FR-FT5  | RE6.3, RE6.4 |
| FR-EN6  | RB2.1      | FR-FT6  | RF4.1, RF4.2 |
| FR-EN7  | RB1.1, RB1.2 | FR-FT7 | RE7.1      |
| FR-CF1  | RG1.1, RG1.5 | Proto: ROLE_ASSIGN.game_config | RF1.1–RF1.3 |
| FR-CF2  | RG1.3      | Proto: ROLE_ASSIGN.role | RF2.* |
| FR-EX1  | RJ2.1, RJ4.1 | Proto: GAME_START | RF3.1 |
| FR-EX2  | RJ2.2      | Proto: MOVE_REQUEST.legal_moves | RB4.1, RE1.1 |
| FR-EX3  | RJ2.3      | Proto: MOVE_SUBMIT.move | RA3.* |
| FR-EX4  | RJ3.1      | Proto: STATE_UPDATE.state | RE3.1 |
| FR-EX5  | RJ4.2      | Proto: GAME_OVER.final_state | RE4.2 |
| FR-EX6  | RJ2.1      | Proto: ERROR codes | RG2.1, RE2.4, RE6.3 |
| FR-EX7  | RJ4.3      |         |            |
