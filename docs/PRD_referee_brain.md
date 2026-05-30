# PRD — Referee Brain (Cognition Engine)

| Field    | Value                                       |
|----------|---------------------------------------------|
| Document | `PRD_referee_brain.md`                      |
| Project  | `agent-arena`                               |
| Version  | 1.00                                        |
| Date     | 2026-05-30                                  |
| Status   | Draft — pending approval before development |
| Author   | Khaled                                      |

> Companion documents: [PLAN_referee.md](PLAN_referee.md) · [TODO_referee.md](TODO_referee.md)
> Sibling documents: [PRD_referee.md](PRD_referee.md) · [PRD_player.md](PRD_player.md)
> **Source of truth:** This PRD transcribes the referee cognition design ledger decisions.

---

## 1. Purpose & Scope

The referee is the central moderator and judge of the PRO/CON persuasion debate. While the general orchestration (socket management, client registration, game loop states) is handled by the referee app and debate engine, the **referee brain** handles the core *cognitive* tasks of the referee process.

Specifically, the referee brain is responsible for:
1. **Turn Evaluation:** Checking semantic legality (concessions) and scoring an individual turn's utterance across the four rubric criteria, producing a number-free qualitative tell.
2. **Verdict Rendering:** Aggregating per-turn scores to compute the final scores, margin, winner, and a holistic rationale at the end of the match.

This PRD specifies the abstract contract for referee cognition and the two concrete implementations: a deterministic `SimpleRefereeBrain` for offline, cost-free testing, and an AI-backed `LLMRefereeBrain` using Google Gemini.

---

## 2. Problem Statement

Without a modular referee brain abstraction, the system suffers from the following:
- **Coupling of loop orchestration and AI cognition:** Unable to test the socket protocol, retry policies, or state management without hitting live API endpoints.
- **Flaky/Non-deterministic tests:** Live LLM scoring is non-deterministic and slow, making CI/CD pipelines unreliable and expensive.
- **Inability to compare judge defenses:** Cannot evaluate naive vs. hardened vs. structural defenses under the same game engine.

---

## 3. Goals

| ID     | Goal                                                                                         |
|--------|----------------------------------------------------------------------------------------------|
| RB-G1  | Define a stateless, pure-function `RefereeBrain` interface.                                  |
| RB-G2  | Implement a cost-free, deterministic `SimpleRefereeBrain` using scripted rules.              |
| RB-G3  | Implement `LLMRefereeBrain` supporting Google Gemini with structured Pydantic outputs.        |
| RB-G4  | Provide three judge variants (naive, hardened, structural) to test defense capability.       |
| RB-G5  | Support structural verification (evidence grounding checks) to override scores when violated. |

---

## 4. Functional Requirements

### 4.1 Referee-brain Contract (FR-RC)
- **FR-RC1 · Stateless ABC:** `RefereeBrain` is a stateless abstract base class with a single method: `decide(context: RefereeContext) -> RefereeDecision`. It holds no mutable match state across calls.
- **FR-RC2 · Two Consultation Moments:** Dispatched via `context.request_kind` using `RequestKind` enum:
  - `EVALUATE_TURN`: Fired after a move passes Tier-1 checks. Returns validity, tell, and turn scores.
  - `RENDER_VERDICT`: Fired at match terminal. Returns the complete verdict.
- **FR-RC3 · `RefereeContext` (Input):** Contains `{request_kind, state (public state dict), move (utterance under review), rubric (criteria+weights), judge_variant, evidence_pack, score_trajectory}`. Never serialized to the wire.
- **FR-RC4 · `RefereeDecision` (Output):** Kind-shaped: `{legal, flag, tell, turn_scores, verdict}`.

### 4.2 `SimpleRefereeBrain` (FR-SB)
- **FR-SB1 · Pure Determinism:** Scripted with no external calls (no network, disk, clock, or RNG).
- **FR-SB2 · Concession Scan:** In `EVALUATE_TURN`, runs a case-folded check for concession keywords (e.g., `"i concede"`, `"i give up"`, `"you win"`, `"i forfeit"`, `"i surrender"`, `"i admit defeat"`). If found, returns `legal=False` and `flag="concession"`.
- **FR-SB3 · Word-Count Normalized Scoring:** Computes scores as `s = round(min(word_count / word_cap, 1.0) * 10, 2)`. Assigns identical scores across all 4 criteria.
- **FR-SB4 · Number-Free Tell:** Returns `tell = f"[T{t} {side}/{phase}] acknowledged — {wc} words."`.
- **FR-SB5 · Deterministic Verdict Aggregate:** Computes final criterion scores as the mean of per-turn scores, applying weights. Breaks ties by greater cumulative word count, then defaults to "PRO".

### 4.3 `LLMRefereeBrain` (FR-LB)
- **FR-LB1 · Gemini-backed Cognition:** Inherits from `LLMCallerMixin` and uses `LLMClient` to invoke Gemini (`gemini-2.5-flash-lite` by default).
- **FR-LB2 · Structured JSON Outputs:** Leverages Pydantic schemas to parse JSON responses:
  - `TurnEvaluationResult`: `{tell: str, logic_score: float, evidence_score: float, rebuttal_score: float, persuasion_score: float}`.
  - `HolisticTiebreakResult`: `{winner: str, rationale: str}`.
  - `HolisticRationaleResult`: `{rationale: str}`.
- **FR-LB3 · Verification of Grounding (Arm-3 Only):** When `judge_variant == "structural"`, runs `_verify_grounding(text, evidence_pack)`. If verification fails, overrides `evidence_score` to `0.0`.

### 4.4 Grounding Verification Algorithm (FR-GV)
The `_verify_grounding` method performs a multi-step check:
1. **Citation Extraction:** Finds all potential citation tokens of format `doc_` or `doc-` (case-insensitive) in the player's text.
2. **Key Validation:**
   - If any extracted token does not match a key in the `evidence_pack`, verification fails.
   - If no valid keys from the `evidence_pack` are cited in the text, verification fails.
3. **Content Overlap Check:** For each cited key, extracts the document's content (title/text), cleans the words (omitting digit-only words, stopwords, and the document ID itself), and verifies there is a non-empty word overlap with the player's text. If no significant words overlap, verification fails.

### 4.5 3-Arm Judging Gradient (FR-JG)
- **FR-JG1 · Naive (Arm-1):** Prompts the LLM to score based on criteria. Susceptible to sycophancy, authority, bandwagon, and fallacy manipulation.
- **FR-JG2 · Hardened (Arm-2):** Instructs the LLM prompt to actively discount manipulation attempts (sycophancy, fabricated credentials, claims of consensus, logical fallacies).
- **FR-JG3 · Structural (Arm-3):** Combines the hardened prompt with the code-enforced grounding check (FR-GV).

---

## 5. Acceptance Criteria

| ID     | Criterion                                                                                           | Target |
|--------|-----------------------------------------------------------------------------------------------------|--------|
| RB-AC1 | **Stateless Interface:** Brain implementations store no match state; all inputs arrive in `RefereeContext`. | Pass   |
| RB-AC2 | **No-LLM Simple Brain:** `SimpleRefereeBrain` operates deterministically with zero network calls.   | Pass   |
| RB-AC3 | **Pydantic Serialization:** `LLMRefereeBrain` extracts JSON responses strictly conforming to schemas. | Pass   |
| RB-AC4 | **Arm-3 Grounding Override:** Under the structural variant, fabricated/ungrounded citations force `evidence_score` to `0.0`. | Pass   |
| RB-AC5 | **No Magic Strings:** Model names, variants, and criteria weights are fully configurable.            | Pass   |
| RB-AC6 | **Ruff & Pytest Clean:** Code and test coverage comply with project standards (coverage ≥ 85%).     | Pass   |

---

## 6. Non-Goals / Out of Scope

- Curating the actual motion pool or compiling external evidence corpuses.
- Managing player network connections, thread watchdogs, or retry loops (these belong to `referee_app` / `game_loop`).
- Evaluating the qualitative success of the prompts outside of empirical sweep results.
