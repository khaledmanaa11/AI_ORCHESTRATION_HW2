# PRD — Submission Finalization

| Field    | Value                                       |
|----------|---------------------------------------------|
| Document | `PRD_submission.md`                         |
| Project  | `agent-arena`                               |
| Version  | 1.00                                        |
| Date     | 2026-05-28                                  |
| Status   | Draft — pending approval before execution   |
| Author   | Khaled                                      |

> Companion documents: [PLAN_submission.md](PLAN_submission.md) · [TODO_submission.md](TODO_submission.md)
> Parent: [PRD.md](PRD.md) · [PLAN.md](PLAN.md) · [CURRENT_STATE.md](CURRENT_STATE.md)
> Motivating context: Run 3 devlog ([2026-05-28-run3-forfeit-surfaced-but-503-still-bites.md](devlog/2026-05-28-run3-forfeit-surfaced-but-503-still-bites.md)) and the now-merged API Gatekeeper ([PRD_api_gatekeeper.md](PRD_api_gatekeeper.md)).

---

## 1. Purpose & Scope

This document specifies the **final stretch from code-complete to assignment-submittable**.
Everything before this triplet is feature work; everything in this triplet is
**evidence, polish, and report**. No new mechanism, subsystem, or transport change
is in scope.

In scope:

1. Validate the post-gatekeeper code path on a real live match (**Run 4**) — done in
   parallel with this document; outcome feeds §4.
2. Execute the Module J sweep (~250–400 matches) against the locked primary motion
   and the primary evidence pack.
3. Produce a written analysis in `notebooks/analysis.ipynb`.
4. Fix the known `[referee tell]` side-label bug.
5. Polish `README.md` to pass the guidelines §2.1 checklist and write
   `docs/PROMPTS.md` (T0.5 / TC.6).
6. Final gate: `uv run pytest`, `ruff check`, file-size check, README review,
   handoff snapshot in `CURRENT_STATE.md`.

Out of scope:

- Any new feature, brain, or transport change.
- Multi-machine deployment or operator-facing UI work.
- Adaptive RPM tuning, persisted RPD counters, multi-provider support
  (already declared out of scope by [PRD_api_gatekeeper.md §11](PRD_api_gatekeeper.md)).

---

## 2. Status of Preceding Work (as of 2026-05-28)

This PRD treats everything below as **DONE**. The gatekeeper triplet is the last
pre-submission feature work.

| Module / Phase                                    | Status | Evidence |
|---------------------------------------------------|--------|----------|
| Phase 0 — Documentation & scaffolding             | ✅ done | `docs/PRD.md`, `docs/PLAN.md`, `docs/TODO.md`, `pyproject.toml`, `uv.lock` |
| Phase 1 — Foundation (config, logging, constants) | ✅ done | T1.1–T1.5 in [TODO.md](TODO.md) |
| Phase 2 — Transport (channel/framing/TCP)         | ✅ done | T2.1–T2.5 in [TODO.md](TODO.md) |
| Phase 3 — Protocol (envelope/codec/validation)    | ✅ done | T3.1–T3.5 in [TODO.md](TODO.md) |
| Phase 4 — Referee (engine, brains, game loop)     | ✅ done | T4.1–T4.8; T4.2 replaced by `DebateEngine`; T4.9 integrated |
| Phase 5 — Player (brain, agent, client)           | ✅ done | T5.1–T5.4 |
| Phase 6 — SDK + entry points + integration test   | ✅ done | `uv run referee`, `uv run player`; AC3 reproducible |
| Phase 7 — LLM brains (Gemini)                     | ✅ done | First clean live match `a308b937-…` on 2026-05-28 paid tier |
| Module J — Sweep runner + evidence pack plumbing  | ✅ done | sweep harness wired; full sweep run is pending in §4 below |
| API Gatekeeper subsystem                          | ✅ done | Commits `1dfc940`, `f89ad0c`; awaits live validation in Run 4 |
| Cross-cutting TC.1–TC.4                           | ✅ done | 272 passing, 94.19 % coverage, ruff clean, no hardcoded ops values |
| Cross-cutting TC.5 (README polish)                | 🟡 partial | Stub present; final pass is a deliverable of this PRD |
| Cross-cutting TC.6 (`docs/PROMPTS.md`)            | ❌ pending | Authored as deliverable of this PRD |
| Cross-cutting TC.7 (annotated match log + diagram)| 🟡 partial | Devlogs cover 2026-05-26 and 2026-05-28 incidents; one architecture diagram still owed |
| Cross-cutting TC.8 (analysis notebook)            | ❌ pending | Authored as deliverable of this PRD |

The post-submission work is bounded by the rows marked 🟡/❌ above plus the Run 4
gate and the Module J sweep itself.

---

## 3. Goals

| ID    | Goal                                                                                                       |
|-------|------------------------------------------------------------------------------------------------------------|
| S-G1  | Run 4 demonstrates the gatekeeper absorbs a 4-burst 503 cluster without surfacing a `quota_aborted` flag, OR if quota_aborted is surfaced, it is correctly labelled (not silent forfeit). |
| S-G2  | A Module J sweep of ≥ 250 completed matches lands in `results/sweep_001/` with one trajectory per match.   |
| S-G3  | `notebooks/analysis.ipynb` runs end-to-end against `results/sweep_001/` and produces the figures and the written discussion required by the assignment rubric. |
| S-G4  | `README.md` satisfies the guidelines §2.1 checklist (install, usage, examples, config guide, contribution notes, license).  |
| S-G5  | `docs/PROMPTS.md` exists and contains the prompt-engineering log entries for at least the referee judge prompt and both player brain prompts. |
| S-G6  | The `[referee tell]` side-label bug from §6 of CURRENT_STATE is fixed and covered by a regression test.    |
| S-G7  | One annotated architecture diagram lives under `assets/` and is referenced from README and PLAN.           |
| S-G8  | Final gate passes: `uv run pytest -q` green, coverage ≥ 85 %, `ruff check` clean, every file ≤ 150 code lines. |
| S-G9  | `CURRENT_STATE.md` records the submission snapshot: branch, commit, sweep ID, notebook path, known caveats. |

---

## 4. Acceptance Criteria

| ID      | Criterion                                                                                                                                   | Target |
|---------|---------------------------------------------------------------------------------------------------------------------------------------------|--------|
| S-AC1   | Run 4 verdict JSON either (a) contains zero `quota_aborted` flags AND zero `timeout` flags, or (b) any capacity exhaustion is surfaced with the loud banner from [PRD_api_gatekeeper.md FR-INT-V2](PRD_api_gatekeeper.md) — never a silent forfeit. | Pass |
| S-AC2   | Module J sweep completes ≥ 250 matches; at most 2 % of matches end in `quota_aborted`.                                                       | Pass |
| S-AC3   | `notebooks/analysis.ipynb` reports: per-side win-rate, margin distribution, turn-count distribution, forfeit/quota-abort rate, best_of_N effect. | Pass |
| S-AC4   | Notebook narrative discusses at least one non-obvious finding tied to a specific cell output (no hand-waving).                              | Pass |
| S-AC5   | README contains: install, three-terminal usage, all `setup.json` fields, sweep usage, troubleshooting (quota, 503), contribution notes, license. | Pass |
| S-AC6   | `docs/PROMPTS.md` has ≥ 3 entries; each entry has context, prompt excerpt, observed output behavior, and the lesson that changed the prompt. | Pass |
| S-AC7   | A regression test asserts that, for a synthetic 10-turn debate, every `[referee tell]` line names the correct side.                          | Pass |
| S-AC8   | At least one architecture diagram under `assets/` (PNG or SVG) is referenced from `README.md` and from `PLAN.md`.                            | Pass |
| S-AC9   | `uv run pytest -q` reports 0 failures, coverage ≥ 85 %.                                                                                      | Pass |
| S-AC10  | `ruff check src tests` reports 0 violations.                                                                                                | Pass |
| S-AC11  | No source file exceeds 150 code lines (AC7).                                                                                                 | Pass |
| S-AC12  | The `CURRENT_STATE.md` "Phase State" section is rewritten with one line: `Submission-ready snapshot taken at <commit> on <date>`.            | Pass |

---

## 5. Functional Requirements

### 5.1 Run 4 — gatekeeper live validation

| ID      | Requirement |
|---------|-------------|
| FR-R4-1 | Run 4 uses `--brain llm` for the referee and `--brain llm` for both players. |
| FR-R4-2 | The match trajectory is saved under `results/` with its match-id filename, untouched. |
| FR-R4-3 | A short devlog `docs/devlog/2026-05-28-run4-gatekeeper-live.md` records: command, observed 503 bursts (count and length), whether the breaker tripped, verdict, gatekeeper `snapshot()` from the verdict JSON. |
| FR-R4-4 | If Run 4 surfaces `quota_aborted`, it counts as a *success* of the gatekeeper, not a regression — the contrast against Run 3's silent-forfeit pattern is the whole point. |
| FR-R4-5 | After Run 4, `CURRENT_STATE.md` "Last Verification" is updated with the Run 4 commit + match-id. |

### 5.2 Module J sweep

| ID      | Requirement |
|---------|-------------|
| FR-SW-1 | Sweep size: 250–400 matches. Default = 250; operator may raise. |
| FR-SW-2 | Evidence pack: `data/evidence_pack_primary.json`. |
| FR-SW-3 | Output directory: `results/sweep_001/` (one trajectory per match, plus one `summary.json`). |
| FR-SW-4 | Sweep runner respects the gatekeeper — when `GatekeeperExhaustedError` is raised, the sweep halts cleanly, writes a partial `summary.json`, and exits non-zero. |
| FR-SW-5 | `summary.json` fields: `total_matches`, `completed`, `forfeited`, `quota_aborted`, `pro_wins`, `con_wins`, `mean_margin`, `mean_turns`, `gatekeeper_final_snapshot`. |
| FR-SW-6 | Sweep can be re-run idempotently into a new directory (`sweep_002/`, …) without overwriting prior data. |

### 5.3 Analysis notebook

| ID       | Requirement |
|----------|-------------|
| FR-NB-1  | Notebook path: `notebooks/analysis.ipynb`. |
| FR-NB-2  | Notebook reads `results/sweep_001/summary.json` plus the per-match trajectories; paths are parameterized at the top, not hardcoded. |
| FR-NB-3  | Notebook produces: side win-rate bar, margin histogram, turn-count histogram, forfeit/quota-abort breakdown, best_of_N comparison. |
| FR-NB-4  | One markdown cell discusses the non-obvious finding tied to a specific figure. |
| FR-NB-5  | Notebook runs top-to-bottom with no errors on a fresh `uv run jupyter` kernel. |
| FR-NB-6  | A regenerated `notebooks/analysis.html` (`jupyter nbconvert --to html`) is checked in alongside the `.ipynb`. |

### 5.4 `[referee tell]` side-label fix

| ID       | Requirement |
|----------|-------------|
| FR-BUG-1 | Locate the label-swap in the referee's turn-summary path (per CURRENT_STATE §Known Minor Bug). |
| FR-BUG-2 | Add a unit test that drives the turn-summary function with a known PRO/CON sequence and asserts the emitted `tell` text names the correct side for each turn. |
| FR-BUG-3 | Test fails on `master` before the fix and passes after. |
| FR-BUG-4 | Fix landed as a single small commit; no incidental refactors. |

### 5.5 README polish (TC.5)

| ID       | Requirement |
|----------|-------------|
| FR-RM-1  | Section: **Installation** — Python version, `uv sync`, `.env` from `.env-example`. |
| FR-RM-2  | Section: **Usage** — three-terminal startup (simple-brain variant and llm-brain variant); sweep runner usage; how to read the verdict; how to inspect a trajectory file. |
| FR-RM-3  | Section: **Configuration** — every `setup.json` field with one-line description and default value, including the new `llm.gatekeeper` block. |
| FR-RM-4  | Section: **Examples & screenshots** — at least one transcript snippet and one figure from the analysis notebook. |
| FR-RM-5  | Section: **Troubleshooting** — `429` quota, `503` capacity, `GatekeeperOpenError`, `GatekeeperExhaustedError`, port-in-use. |
| FR-RM-6  | Section: **Contribution & code style** — `ruff`, file ≤ 150 lines, TDD expectation, devlog discipline. |
| FR-RM-7  | Section: **License & credits**. |

### 5.6 PROMPTS log (T0.5 / TC.6)

| ID       | Requirement |
|----------|-------------|
| FR-PL-1  | File at `docs/PROMPTS.md` with a header describing what the log is for. |
| FR-PL-2  | One entry per significant prompt: referee judge prompt, PRO player brain prompt, CON player brain prompt, sweep evidence-pack instruction. |
| FR-PL-3  | Each entry fields: **Date**, **Context**, **Prompt excerpt**, **Observed behavior**, **Change made**, **Why**. |
| FR-PL-4  | Entries are kept current — last entry's date matches the most recent prompt change in source. |

### 5.7 Architecture diagram (TC.7)

| ID       | Requirement |
|----------|-------------|
| FR-AD-1  | One process / message-flow diagram exported under `assets/` as PNG or SVG (Mermaid source acceptable as the `.mmd` file alongside). |
| FR-AD-2  | Diagram shows: referee process, player A, player B, TCP connections, Gemini API, gatekeeper, evidence pack, results directory. |
| FR-AD-3  | Referenced from `README.md` and from `PLAN.md` §1. |

### 5.8 Final gate & handoff

| ID       | Requirement |
|----------|-------------|
| FR-GT-1  | Final gate command sequence runs from a clean checkout: `uv sync && uv run pytest -q && uv run ruff check src tests`. |
| FR-GT-2  | The gate output is appended to `docs/devlog/2026-05-28-submission-gate.md`. |
| FR-GT-3  | `CURRENT_STATE.md` is rewritten to a short submission snapshot: branch, commit, sweep ID, notebook path, known caveats, run-from-scratch command. |

---

## 6. Non-Functional Requirements

| ID      | Requirement |
|---------|-------------|
| S-NFR1  | No new top-level dependency added unless justified in this PRD (notebook deps already in `pyproject.toml`). |
| S-NFR2  | No `.env`, secret, or API key ever leaves the local machine — sweep outputs are scrubbed of keys before commit. |
| S-NFR3  | Sweep wall-clock time budget: ≤ 6 hours unattended on the paid tier (operator can interrupt; partial sweep is acceptable per FR-SW-4). |
| S-NFR4  | Cost guardrail: $15 GCP budget alert remains in place; abort if alert fires. |
| S-NFR5  | All deliverables (sweep dir, notebook outputs, devlogs) are reproducible from `master` HEAD without ad-hoc local state. |

---

## 7. Out of Scope

- A second-pass sweep with a different motion or evidence pack — single sweep is enough for the assignment.
- Multi-model comparison (only `gemini-2.5-flash` for the sweep).
- Any CI / GitHub Actions integration — local gate only.
- Web UI, dashboards, or interactive analysis app.
- Cross-platform packaging (Windows-only paid-tier run is the submission target).

---

## 8. Risks

| Risk                                                | Mitigation                                                                                  |
|-----------------------------------------------------|---------------------------------------------------------------------------------------------|
| Sweep midway hits paid-tier RPD                     | Gatekeeper raises `GatekeeperExhaustedError`; FR-SW-4 ensures a clean halt with partials.   |
| GCP budget alert fires                              | Operator pauses the sweep; analysis runs on whatever ≥ 250 matches were completed.          |
| Run 4 reveals a gatekeeper bug                      | Fix lands as a small follow-up commit; sweep does not start until Run 4 is green.            |
| Notebook depends on undocumented trajectory fields  | FR-NB-2 parameterizes paths; trajectory schema is read from `services/referee/result.py`.   |
| `[referee tell]` fix breaks an existing test        | TDD: the regression test in FR-BUG-2 lands first; surrounding tests pinned via golden files.|

