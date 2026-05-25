# Design Agenda — Referee + Debate Game

| Field    | Value                                      |
|----------|--------------------------------------------|
| Document | `DESIGN_AGENDA.md`                         |
| Project  | `agent-arena`                              |
| Date     | 2026-05-25                                 |
| Status   | S1–S9 LOCKED — next = S10 (write the triplet) |

> This is a plan for **deciding**, not for coding. It sequences the design sessions that
> take us from mid-discussion to "every choice made & recorded," at which point we write
> the `PRD_referee` + `PLAN_referee` + `TODO_referee` triplet and hand off to a coding session.
> Running decisions live in [DESIGN_LEDGER.md](DESIGN_LEDGER.md).

---

## End state (definition of done)
A complete **Decision Ledger**: every atomic decision across the tracks has a recorded
answer — enough that writing the doc triplet is transcription, not new thinking.

## The concrete game (what we are building)
A structured **PRO/CON persuasion debate**. Two LLM players argue a motion; one is assigned
PRO, one CON (sides hidden until the match starts). The **referee** moderates (directs the
debate, flags weak turns) and **judges** (declares a single winner at the end).

**Intellectual centerpiece (Option B):** a working implementation of **AI Safety via Debate /
debate-as-oversight** (Irving et al. 2018; Anthropic 2025), where the open question is whether
the LLM judge is convinced by *truth* or by the better *manipulator*. We lean INTO judge
manipulation — both players model and exploit the referee (inspiration: the persuasion RCT,
Nature Human Behaviour 2025, where personalization was the dominant lever; and the TV series
*The Mentalist* — cold-read the subject, then lead them). We **measure** manipulability via an
ablation (manipulation tools on vs off → win-rate delta; naive judge vs bias-hardened judge).

---

## Ordered sessions

Hard rule driving the order: **decide the judge before the players** — the players' top weapon
is reading/exploiting the judge, which can't be specced until the rubric exists.

| # | Session | Tracks | Exit criterion |
|---|---------|--------|----------------|
| **S1** | Debate format & turn skeleton | 2, 3 | A full turn-by-turn skeleton of one match |
| **S2** | Referee as JUDGE — rubric & verdict *(critical path)* | 6 | The rubric is frozen — the exact thing players exploit |
| **S3** | Referee as MODERATOR — direction & feedback | 5 | Referee's in-debate behavior decided |
| ~~**S4**~~ ✅ | Player powers — finalize the arsenal *(the big one)* | 9 + arm H | **DONE** — arsenal frozen (4a–4j) |
| ~~**S5**~~ ✅ | Game state & move contract | 4, 7 | **DONE** — `DebateState`/`DebateMove` + two-tier legality (5.0/5.4/5.7) |
| ~~**S6**~~ ✅ | Referee-brain decision schema | 8 | **DONE** — stateless `decide(ctx)->decision`, 2 kinds, variant strategy, trajectory-aggregate verdict (6.0/6.a–i) |
| ~~**S7**~~ ✅ | Protocol & config mapping | 10, 11 | **DONE** — ZERO protocol diff (version `"1.00"`, no new type/payload field, AC9); debate rides generic slots; `debate` config block recorded (7.a–7.j) |
| ~~**S8**~~ ✅ | Edge cases & experiment design | 12, 14 | **DONE** — verdict-reachability fault policy (8.1–8.6, zero new infra) + the ON-vs-OFF × 3-judge sweep, mirror pairs, READ-accuracy test, 5 hypotheses (8.7–8.15) |
| ~~**S9**~~ ✅ | Phase-1 placeholder | 13 | **DONE** — full scripted `SimpleRefereeBrain` (9.a–9.i): pure/stateless `decide()`, concession-only Tier-2, word-count scores, deterministic 6.h verdict; T6.3 runs the real `DebateEngine` to `GAME_OVER` pre-LLM |
| **S10** *(next)* | Consolidate → write the triplet | — | `PRD_referee` + `PLAN_referee` + `TODO_referee` written |

---

## The player arsenal (8 arms — to be finalized in S4)

| Arm | Category | Status |
|-----|----------|--------|
| A | Knowledge & Evidence | menu |
| B | Reasoning scaffolding | Reflexion (B3) = S-tier |
| C | Opponent handling | Steelman-then-refute (C4) = A-tier |
| D | Rhetoric & persuasion | delivery layer |
| E | Strategy & memory | menu |
| F | Game awareness | Rubric awareness (F1) = S-tier (depends on S2) |
| G | Persona & conviction | cheap wins |
| **H** | **Judge Exploitation ("The Mentalist")** | **centerpiece** — READ (cold-read judge) + CONTROL (exploit documented LLM-judge biases) |

> ✅ S4 CLOSED — arsenal frozen (4a–4j in [DESIGN_LEDGER.md](DESIGN_LEDGER.md)). arm-H CONTROL vectors pinned to
> citations (CALM/*Justice or Prejudice?* 2410.02736; position-bias 2406.07791; self-preference 2410.21819;
> sycophancy 2604.21564). Final kit: 4 CONTROL tools (Sycophancy/Authority/Bandwagon/Fallacy-oversight) +
> Verbosity-density; READ judge-profile; Reflexion; Steelman; shared evidence pack; Best-of-N (judge-profile
> select); adaptive persona; F1 rubric-awareness; ablation line β. Position bias → demoted to an S8 measured variable.

## Foundational principles (locked)
- **Symmetric loadout** — both players get the identical kit, opposite sides.
- **Public vs private** — only the final utterance travels the wire; all thinking/planning/notes stay inside the player process.
