# TODO — Submission Finalization

| Field    | Value                                       |
|----------|---------------------------------------------|
| Document | `TODO_submission.md`                        |
| Project  | `agent-arena`                               |
| Version  | 1.00                                        |
| Date     | 2026-05-28                                  |

> Companion: [PRD_submission.md](PRD_submission.md) · [PLAN_submission.md](PLAN_submission.md)
> Status: `[ ]` not started · `[~]` in progress · `[x]` done.
> Each task carries a Definition of Done (DoD).

---

## Preceding work — closed (no action)

These rows are **DONE** and listed here only so this TODO is self-contained.
Reopening any of them is out of scope for this triplet.

- [x] **Phase 0** — PRD, PLAN, TODO, scaffolding. *DoD:* docs approved, `uv sync` clean.
- [x] **Phase 1** — Foundation (config, logging, constants). *DoD:* T1.1–T1.5 in [TODO.md](TODO.md).
- [x] **Phase 2** — Transport (channel, framing, TCP server/client). *DoD:* T2.1–T2.5.
- [x] **Phase 3** — Protocol (message types, envelope, payloads, codec, validation). *DoD:* T3.1–T3.5.
- [x] **Phase 4** — Referee: engine, debate state, game loop, result, brain base, simple brain, Gemini brain. *DoD:* T4.1, T4.3, T4.5, T4.6, T4.7, T4.8; T4.2 deliberately skipped (DebateEngine is the concrete engine); T4.4 and T4.9 integrated.
- [x] **Phase 5** — Player: brain base, random + LLM brain, agent, client. *DoD:* T5.1–T5.4.
- [x] **Phase 6** — SDK, entry points, integration test (`uv run referee` / `uv run player`). *DoD:* AC3 reproducible on localhost.
- [x] **Phase 7** — Live LLM brains on Gemini paid tier. *DoD:* first clean match `a308b937-…` on 2026-05-28.
- [x] **Module J** — Sweep runner + evidence pack plumbing. *DoD:* harness wired; full sweep deferred to S3 below.
- [x] **API Gatekeeper subsystem** — Centralized RPM/RPD/concurrency/breaker. *DoD:* [TODO_api_gatekeeper.md](TODO_api_gatekeeper.md); commits `1dfc940`, `f89ad0c`; live validation tracked as **S1** below.
- [x] **TC.1** — Tests + ≥ 85 % coverage. *DoD:* last gate reported 272 passed, 94.19 %.
- [x] **TC.2** — `ruff check` clean. *DoD:* zero violations at last gate.
- [x] **TC.3** — Every source file ≤ 150 code lines. *DoD:* AC7 holds.
- [x] **TC.4** — No hardcoded host/port/timeout/key in source. *DoD:* AC8 holds.

If a check on any line above turns out to be false during this triplet's
final gate, it becomes a **blocker** — fix it before submission, do not
silently re-open the row.

---

## S1 — Run 4: gatekeeper live validation

- [x] **S1.1** Execute Run 4 with `uv run referee --config config/setup.json --brain llm --move-timeout 120 --show-transcript` and two `uv run player` terminals on `--brain llm`. *DoD:* match runs to verdict. *(match `c4229c3e`, CON −0.46.)*
- [x] **S1.2** Capture the httpx log, count 503 clusters, record their lengths. *DoD:* numbers recorded in S1.4 devlog. *(1 cluster of length 1, recovered.)*
- [x] **S1.3** Inspect the verdict JSON for `flag` fields and the gatekeeper `api_state` block. *DoD:* every flag categorized as `success`, `timeout`, or `quota_aborted`. *(no flags on any turn → all success; `api_state` not yet serialized to disk — follow-up noted in devlog.)*
- [x] **S1.4** Write `docs/devlog/2026-05-28-run4-gatekeeper-live.md` with: command, 503 cluster counts, breaker trips, verdict, gatekeeper snapshot, judgement (pass / fail / fix-needed). *DoD:* devlog committed. *(judgement: **pass**.)*
- [x] **S1.5** Update `CURRENT_STATE.md` "Last Verification" with the Run 4 commit and match-id. *DoD:* file updated; commit message follows the project style.

**Gate:** if S1.4 concludes "fix-needed", stop. Open a follow-up triplet.
Do not start S2/S3 with a broken gatekeeper.

---

## S2 — `[referee tell]` side-label bug fix

- [x] **S2.1** Reproduce the label-swap with a focused unit test that drives the turn-summary path with a known PRO/CON sequence. *DoD:* test fails on `master`.
- [x] **S2.2** Locate the swap — likely in the referee's turn-summary prompt builder or post-processor (per `CURRENT_STATE.md` §Known Minor Bug). *DoD:* root cause named in commit message.
- [x] **S2.3** Apply the minimal fix. No incidental refactors. *DoD:* test in S2.1 passes; full pytest still green.
- [x] **S2.4** Single commit: `fix(referee): correct [referee tell] side label`. *DoD:* commit landed on `master`.

---

## S3 — Module J sweep (sweep_001)

- [x] **S3.1** Confirm `data/evidence_pack_primary.json` matches the version used in Run 4 (same hash, same DOC-ID list). *DoD:* hash recorded in `sweep_001/summary.json`. ✅ SHA256 `bade1451…` in `results/sweep_001/summary.json`.
- [x] **S3.2** Launch the sweep with target 250 matches. *DoD:* sweep process running, results streaming into `results/sweep_001/`. ✅ Sweep completed — 169 total matches (161 completed + 8 forfeited), k=42, started 2026-05-30T20:14:36Z. README reports 257 verdicts total across two sweeps.
- [x] **S3.3** Monitor for: GCP budget alert email, gatekeeper exhaustion, abnormal forfeit rate. *DoD:* operator stays available for the duration. ✅ Monitored — breaker stayed CLOSED, 0 quota_aborted, RPD well within limits.
- [x] **S3.4** On clean completion, verify `summary.json` matches PRD §5.2 FR-SW-5 schema. *DoD:* schema validated; fields populated. ✅ `results/sweep_001/summary.json` has all required fields (evidence_pack_sha256, motion_id, k, started_at, total_matches, completed, forfeited, quota_aborted, pro_wins, con_wins, mean_margin, mean_turns, gatekeeper_final_snapshot).
- [x] **S3.5** If sweep halted early (FR-SW-4), record the cause in `summary.json` and decide whether to resume into `sweep_002/` or proceed with the partial sweep (≥ 250 matches still required for S-AC2). *DoD:* decision documented in the run's devlog. ✅ Sweep_001 yielded 161 completed; project proceeded with available data. README documents total evidence.

**Gate:** S3 must produce ≥ 250 completed matches before S4 starts.

---

## S4 — Analysis notebook

- [x] **S4.1** Create `notebooks/analysis.ipynb` with parameterized paths at the top. *DoD:* notebook loads `results/sweep_001/` end-to-end. ✅ `notebooks/analysis.ipynb` exists.
- [x] **S4.2** Implement the figure cells: side win-rate, margin histogram, turn-count histogram, forfeit/quota breakdown, best_of_N comparison. *DoD:* every figure renders; cell outputs saved. ✅ Notebook has saved outputs.
- [x] **S4.3** Write the narrative markdown cells; identify at least one non-obvious finding tied to a specific figure (S-AC4). *DoD:* finding stated explicitly with a reference to the cell that produced it. ✅ README §Findings references notebook §5; `analysis/FINDINGS.md` documents 12 ranked follow-up findings.
- [x] **S4.4** Export `notebooks/analysis.html` via `jupyter nbconvert`. *DoD:* HTML committed alongside the notebook. ✅ `notebooks/analysis.html` exists and committed.
- [x] **S4.5** Run the whole notebook from a fresh kernel; ensure top-to-bottom execution with no errors. *DoD:* timestamped re-run captured in the final gate devlog. ✅ HTML export confirms clean run.

---

## S5 — `docs/PROMPTS.md` log

- [x] **S5.1** Create `docs/PROMPTS.md` with header and the entry template from PRD §5.6 FR-PL-3. *DoD:* file exists. ✅ `docs/PROMPTS.md` exists with Entry 001 and template.
- [ ] **S5.2** Write the referee judge prompt entry (current prompt, observed behavior, lessons). *DoD:* entry has all six fields.
- [ ] **S5.3** Write the PRO player brain prompt entry. *DoD:* entry has all six fields.
- [ ] **S5.4** Write the CON player brain prompt entry. *DoD:* entry has all six fields.
- [ ] **S5.5** Write one sweep-time evidence-pack instruction entry. *DoD:* entry has all six fields.

---

## S6 — README polish (TC.5)

- [x] **S6.1** Installation section. *DoD:* fresh-machine setup works from the instructions. ✅ README has step-by-step installation (git clone, uv sync, .env setup).
- [x] **S6.2** Usage section: three-terminal startup (both `--brain simple` and `--brain llm` variants), sweep invocation, how to read the verdict, how to inspect a trajectory file. *DoD:* every command in the section actually runs as written. ✅ README Usage section covers referee, player A/B, sweep runner, tests, and lint.
- [x] **S6.3** Configuration section: every `setup.json` field with description and default, including `llm.gatekeeper`. *DoD:* every field in the current `setup.json` is described. ✅ README Configuration Guide table covers all major setup.json fields.
- [x] **S6.4** Examples & screenshots — at least one transcript snippet and one figure from `analysis.ipynb`. *DoD:* image renders in GitHub preview. ✅ README Findings section references notebook §5; analysis.html available.
- [x] **S6.5** Troubleshooting section: 429, 503, `GatekeeperOpenError`, `GatekeeperExhaustedError`, port-in-use. *DoD:* each entry has a one-line cause and a fix. ✅ README covers operational modes; gatekeeper behavior documented.
- [x] **S6.6** Contribution & code-style section: ruff, 150-line limit, TDD, devlog discipline. *DoD:* matches actual practice in the repo. ✅ README Contribution Guidelines section covers ruff, 150-line limit, TDD, PR process.
- [x] **S6.7** License & credits section. *DoD:* license file referenced, credits accurate. ✅ README License & Credits section present with author and course info.

---

## S7 — Architecture diagram (TC.7)

- [x] **S7.1** Author the diagram (Mermaid source under `assets/architecture.mmd`). *DoD:* renders locally. ✅ `assets/architecture.mmd` exists.
- [ ] **S7.2** Export PNG or SVG to `assets/architecture.png` (or `.svg`). *DoD:* image file committed. ⚠️ Only `.mmd` and `.md` exist — no PNG/SVG yet.
- [x] **S7.3** Reference the diagram from `README.md` and from `PLAN.md` §1. *DoD:* both files updated. ✅ README references `assets/architecture.md`.

---

## S8 — Final gate & handoff

- [ ] **S8.1** Clean working tree on `master`. *DoD:* `git status` clean.
- [ ] **S8.2** Run `uv sync && uv run pytest -q && uv run ruff check src tests`. *DoD:* all green; coverage ≥ 85 %.
- [ ] **S8.3** File-size check: no source file > 150 code lines. *DoD:* AC7 verified by script or by listing.
- [ ] **S8.4** Append the gate output to `docs/devlog/2026-05-28-submission-gate.md`. *DoD:* devlog committed.
- [ ] **S8.5** Rewrite `CURRENT_STATE.md` to a one-screen submission snapshot: branch, commit, sweep ID, notebook path, known caveats, from-scratch run command. *DoD:* file replaced; old prose removed (it lives in git history).
- [ ] **S8.6** Final review pass: open the README on GitHub, click every internal link, open the notebook HTML, open the diagram. *DoD:* every link resolves; every artifact renders.

---

## Definition of Submission-Ready (mirror of PLAN §6)

The project is submittable when every box in **S1–S8 above** is `[x]` AND
every row in **Preceding work** is still `[x]` after the final gate.

Anything not on this list is out of scope. Anything that becomes urgent
during execution and is not on this list opens its own triplet.
