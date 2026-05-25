# Architecture Plan — Referee & Debate Game

| Field    | Value                                       |
|----------|---------------------------------------------|
| Document | `PLAN_referee.md`                           |
| Project  | `agent-arena`                               |
| Version  | 1.00                                        |
| Date     | 2026-05-25                                  |
| Status   | Draft                                       |

> Companion: [PRD_referee.md](PRD_referee.md) · [TODO_referee.md](TODO_referee.md)
> Decisions source: [DESIGN_LEDGER.md](DESIGN_LEDGER.md) (S1–S9).
> **No source code in this document — structure, interfaces in prose, and diagrams only.**

---

## 1. Overview

The debate specializes the game-agnostic substrate at exactly two seams (`[5.0, 6.0]`):

- the **game** seam — typed `DebateState`/`DebateMove` + a `DebateEngine(GameEngine)`,
  living in `services/game/`, serializing into the substrate's generic dicts;
- the **brain** seam — a `RefereeBrain.decide(context)->decision` contract with two impls
  (`SimpleRefereeBrain`, `LLMRefereeBrain`), living in `services/referee/brain/`.

The referee `game_loop.py` orchestrates; the brain *rules*; the engine holds *mechanics*.
The transport/protocol layers are untouched (`[7.a]`, AC9).

```
        ┌──────────────────────── Referee process ────────────────────────┐
        │                                                                  │
 wire ─►│  game_loop  ──validate──►  DebateEngine   (Tier-1, pure)         │
        │     │                          │                                 │
        │     │ EVALUATE_TURN/RENDER ◄────┘ apply_move / is_terminal        │
        │     ▼                                                            │
        │  RefereeBrain.decide(ctx)  →  {legal, flag, tell, scores|verdict} │
        │     │  (Simple = scripted · LLM = prompt)                         │
        │     ├─ legal? no → ERROR + re-MOVE_REQUEST (retry cap N)          │
        │     ├─ tell      → broadcast STATE_UPDATE (both players)          │
        │     ├─ scores    → private trajectory (loop-owned, off-wire)      │
        │     └─ verdict   → GAME_OVER.final_state + trajectory dump        │
        └──────────────────────────────────────────────────────────────────┘
```

---

## 2. File Structure (new + touched)

```
src/agent_arena/services/game/
├── debate_state.py     ← DebateState, DebateMove, TurnRecord (frozen)   (NEW)
├── debate_engine.py    ← DebateEngine(GameEngine): validate/apply/is_terminal (NEW)
├── engine_base.py      (existing GameEngine ABC — unchanged)
└── trivial_game.py     (existing — stays as the bare ABC smoke test [9.i])

src/agent_arena/services/referee/
├── brain/
│   ├── base.py         ← RefereeBrain ABC + RefereeContext + RefereeDecision (NEW)
│   ├── simple_brain.py ← SimpleRefereeBrain (Phase-1, scripted)          (NEW)
│   └── llm_brain.py    ← LLMRefereeBrain (Phase-7)                       (NEW)
├── game_loop.py        ← debate turn loop, retry gate, fault policy      (wires S3/S8)
└── result.py           ← terminal detection + GAME_OVER + trajectory dump

config/setup.json       ← + version-stamped `debate` block                (S7)
src/agent_arena/constants.py ← + MALFORMED_MESSAGE, config-key tokens      (S7/S8)

results/                ← 3 JSONL streams (verdict / private-capture / metadata)
notebooks/              ← analysis: defense curve, READ-accuracy, flip-rate (TC.8)
tests/integration/      ← real referee + 2 players → GAME_OVER (T6.3)
```

---

## 3. The Generic ↔ Specific Boundary (`[5.0]`)

| Generic substrate slot                 | Specialized debate object               |
|----------------------------------------|-----------------------------------------|
| `state: dict[str,Any]`                 | `DebateState.to_dict()` (public-only)   |
| `move: dict[str,Any]`                  | `DebateMove.to_dict()` = `{"text": …}`  |
| `legal_moves: list[Any]`               | one-element constraint descriptor       |
| `final_state.verdict: dict`            | the 2e verdict dict                     |
| `ROLE_ASSIGN.game_config: dict`        | rubric + format + evidence_pack         |

**Match state vs game state:** lobby/players/`match_id`/lifecycle (game-agnostic) stay in
`services/referee/state.py`; debate-specific state = `DebateState`, owned by `DebateEngine`.
The wire only ever sees plain dicts — substrate generality is preserved.

---

## 4. The `decide()` Interface (in prose, `[6.0–6.i]`)

`RefereeBrain` is an abstract base with one method: `decide(context) -> decision`.

- **Input `RefereeContext`** — `request_kind` (the dispatcher), `state` (public dict),
  `move` (the utterance under review; `None` on verdict), `rubric`, `judge_variant`,
  `evidence_pack`, and `score_trajectory` (the loop-owned prior per-turn scores). The
  context object is **referee-process-internal and never serialized to the wire**, so it
  may carry the private trajectory safely.
- **Output `RefereeDecision`** — one dataclass: `legal`, `flag`, `tell`, `turn_scores`,
  `verdict`. EVALUATE_TURN populates the first four; RENDER_VERDICT populates `verdict`.
- **Statelessness** — the brain holds no mutable match state; identical context in ⇒
  identical decision out. The loop owns the trajectory, injects it each call, appends each
  decision's `turn_scores`, and dumps the full trajectory post-game.

**Why one method + one decision type:** smallest surface to mock (T4.7 DoD) and the exact
same shape for the scripted and LLM brains, so Phase-7 is a dependency-injection swap.

| Brain              | `legal`/`flag`            | `tell`            | `turn_scores`              | `verdict`                  |
|--------------------|---------------------------|-------------------|----------------------------|----------------------------|
| `SimpleRefereeBrain` | concession keyword scan  | number-free template | word-count-normalized     | 6.h aggregate + fixed tiebreak |
| `LLMRefereeBrain`  | LLM off-topic/concession  | LLM reaction      | LLM per-criterion judgment | 6.h aggregate + holistic tiebreak |

---

## 5. Turn-Loop Sequence (happy path)

```
GAME_START (initial_state @ turn 0, turn_order)
loop while not engine.is_terminal():
  active_side = PRO if turn_number odd else CON          [5.4d, deterministic]
  → MOVE_REQUEST (legal_moves descriptor) to active player only
  ← MOVE_SUBMIT {text}
  engine.validate_move()  ── Tier-1 mechanical (no LLM)  [5.7c]
      fail → ERROR{ILLEGAL_MOVE, reason} + re-MOVE_REQUEST (attempt++), shared budget
  brain.decide(EVALUATE_TURN)  ── Tier-2 semantic + tell + turn_scores  [6.a, 6.f]
      legal=False → retry gate (cap N); exhausted → penalized empty TurnRecord
      legal=True  → engine.apply_move() appends TurnRecord
  tell  → broadcast STATE_UPDATE (both players read transcript[-1])     [7.b, 2a-i]
  scores→ append to loop-private trajectory (off-wire)                  [2a, 6.d]
engine.is_terminal() → brain.decide(RENDER_VERDICT, score_trajectory)   [5.4g, 6.h]
  → GAME_OVER.final_state.verdict (2e) + dump trajectory to results/    [7.c, 6.d]
```

---

## 6. Public / Private Boundary (`[4a, 5.4e]`)

The channel **is** the boundary — there is no leak-handling because anything written into
the utterance payload *is* public by definition.

| Direction | PUBLIC (on the wire)                                  | PRIVATE (never leaves the process)                     |
|-----------|------------------------------------------------------|--------------------------------------------------------|
| Player →  | one field: the final utterance (`{text}`)            | scratchpad, READ profile, CONTROL selection, drafts    |
| Referee → | broadcast tells (qualitative) + final verdict        | per-turn numeric trajectory (dumped post-game only)     |

Consequences: the judge scores only the public utterance (product, not scheme); numbers
stay off-wire by construction; private traces dump to `results/` post-game, symmetric with
the judge's trajectory dump — which is what makes the ablation *attributable*.

---

## 7. Fault Cascade (debate policy over existing primitives, `[8.1–8.6]`)

```
post-GAME_START match wrapped in try/finally  ──► GAME_OVER ALWAYS reached [8.6]

move_timeout expires (one budget, shared across retries)
   → penalized empty TurnRecord (flag="timeout"), advance turn, continue  [8.1]
beats flowing + no move = alive-but-silent → penalized skip, KEEP data     [8.2]
beats stopped = dead → watchdog on_timeout → disconnect:
   → forced verdict on partial transcript, tag terminated_reason,
     EXCLUDE from aggregates + re-run same seed                            [8.3]
bad CONTENT frame (codec/validation) → ERROR{MALFORMED_MESSAGE} + drop,
   no turn advance (move_timeout still governs)                            [8.4]
broken STREAM (ConnectionClosed / FrameTooLarge) → escalate to disconnect  [8.4]
pre-GAME_START failure → lobby_timeout → clean abort, NO data cell         [8.5]
```

**The discriminator** between a slow thinker and a dead peer is the heartbeat (a daemon
thread that beats even while the player generates), decoupled from `move_timeout`.

---

## 8. Architecture Decision Records (transcribed from the ledger)

| ADR     | Decision                                                              | Rationale                                                          | Ledger |
|---------|----------------------------------------------------------------------|--------------------------------------------------------------------|--------|
| REF-001 | Typed game objects serialize INTO generic dicts (not protocol payloads) | Substrate stays game-agnostic; wire sees plain dicts (zero diff)   | 5.0, 7.a |
| REF-002 | `turn_number` is the only counter; phase/side/round derived          | Eliminates state drift; deterministic + reproducible               | 5.4d   |
| REF-003 | State-on-wire is public-only; numbers hidden until verdict           | Authentic cold-read surface; uncontaminated DV                     | 5.4e, 2a |
| REF-004 | Stateless brain; loop owns the hidden trajectory                     | Pure function ⇒ reproducible + trivially mockable; numbers off-wire | 6.d    |
| REF-005 | One `decide()` + one `RefereeDecision` type, kind-shaped             | Smallest mock surface; identical shape for Simple & LLM brains     | 6.0, 6.c |
| REF-006 | Judge variant = strategy switch on one class, not subclasses         | Shared machinery; verdict structure identical across arms          | 6.g    |
| REF-007 | Verdict = deterministic aggregate of the trajectory + 2e shape       | Auditable + reproducible; only the rationale prose is free-form    | 6.h    |
| REF-008 | `SimpleRefereeBrain` scores by word-count, identical across criteria | Honest trivial proxy; deterministic; non-degenerate trajectory     | 9.d    |
| REF-009 | Move-timeout = penalized skip, never forfeit; one shared budget      | Honors "no giving up"; preserves the data cell; bounds wall-clock  | 8.1    |
| REF-010 | Verdict-reachability invariant via post-GAME_START try/finally       | Closes both the thread-leak and the missing-data-cell failure modes | 8.6    |
| REF-011 | The whole sweep is config/CLI-driven via a thin runner               | No per-condition source edits (AC8); reproducible by seed          | 7.j, 8.13 |
| REF-012 | Phase-1 runs the REAL DebateEngine (not the trivial game)            | Proves the shipped loop; Phase-7 swaps only brain classes (AC9)    | 9.i    |

---

## 9. Build Order (dependency-ordered; details in TODO_referee.md)

1. **`debate_state.py`** — `DebateState`/`DebateMove`/`TurnRecord` + serializers (no deps).
2. **`debate_engine.py`** — `validate_move`/`apply_move`/`is_terminal` over the state.
3. **`brain/base.py`** — `RefereeBrain` ABC + `RefereeContext`/`RefereeDecision`.
4. **`brain/simple_brain.py`** — the scripted impl (FR-SB1–FR-SB7).
5. **`game_loop.py` debate wiring** — turn loop + retry gate + fault policy (S3/S8).
6. **`config` + `constants`** — the `debate` block + `MALFORMED_MESSAGE` token.
7. **Integration test (T6.3)** — real referee + 2 seeded players → `GAME_OVER` (the gate).
8. **`brain/llm_brain.py`** (Phase-7) — same interface, prompt-driven; DI swap only.
9. **Experiment harness** — sweep runner + `results/` schema + analysis notebook (S8).

The hard gate is step 7: when it passes deterministically, the substrate is proven
game/brain-agnostic and the costly LLM phase is de-risked before a single token is spent.
