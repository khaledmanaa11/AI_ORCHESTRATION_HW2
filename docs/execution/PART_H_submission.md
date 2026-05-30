# PART H — Submission deliverables (LAST)

**Do not start this part until every step in Parts B and C is `[x]`.** The canonical sweep needs
a healthy gatekeeper and wired fault-tolerance, or it dies on an OPEN breaker (that is exactly
what happened in the earlier `sweep_003` run — 242 of 250 matches forfeited). Reference:
`REMAINING_WORK.md` §6. H2 depends on H1.

---

## H1 — Run the canonical ≥250-match sweep into `results/sweep_001/`
**Goal:** Produce the real experiment dataset the submission analyzes, in the directory the PRD
names (`results/sweep_001/`), with most matches actually completing (not forfeited).
**Read first:**
- `src/agent_arena/apps/sweep_runner.py` and `sweep_concurrency.py` (how a sweep is launched, the idempotency guard that refuses a non-empty dir)
- `results/sweep_003/summary.json` (the earlier failed run — read for comparison, do NOT delete)
- `docs/PRD_submission.md` (FR-SW-3: ≥250 matches, output dir)
**Files (scope):** runs commands + writes under `results/sweep_001/` (a NEW dir). No source edits — if a source change is needed, STOP and mark BLOCKED (that belongs in Part E, not here).
**Do:**
1. **`results/sweep_001/` already exists** with an old 12-match test run, and the sweep runner's
   idempotency guard refuses a non-empty dir (raises `SystemExit`). **Do not delete it.** Instead
   rename it to preserve it: `git mv results/sweep_001 results/sweep_001_smoke12` (or a plain
   filesystem move if it isn't tracked). Now `results/sweep_001/` is free.
2. Make sure `GOOGLE_API_KEY` is set and the Gemini paid tier is active (see `docs/gemini_paid_tier`).
3. Launch the sweep targeting `results/sweep_001/` with ≥250 matches.
4. When it finishes, open `results/sweep_001/summary.json` and confirm `completed` is ≥ ~95% of
   `total_matches` and the breaker did not sit OPEN. If a large fraction forfeited, the gatekeeper
   config or quota is wrong — mark this step **BLOCKED** with the numbers; do not fake the data.
**Verify:** `results/sweep_001/summary.json` exists with `completed ≥ 250` (or near it) and a
`stream_a_trajectory.jsonl` present.
**Commit:** `data(sweep): canonical >=250-match sweep in results/sweep_001`
> Note: this commits experiment outputs. That matches this repo's "commit everything" rule. If the
> files are very large, confirm they aren't `.gitignore`d before assuming the commit captured them.

---

## H2 — Rewrite `notebooks/analysis.ipynb`
**Goal:** A notebook that reads the real `sweep_001` data (not mock values), parameterized at the
top, with the required figures, exported to HTML.
**Read first:**
- `notebooks/analysis.ipynb` (current state: hardcoded `../results/stream_a_trajectory.jsonl`, mock `win_rates`, no saved outputs)
- `results/sweep_001/summary.json` + `stream_a_trajectory.jsonl` (from H1) and `stream_b_*`/`stream_c_*` (from Part E)
- `docs/PRD_submission.md` (FR-NB-2/3/5 — required cells/figures)
**Files (scope):** `notebooks/analysis.ipynb`, new `notebooks/analysis.html`.
**Do:**
1. Add a top cell defining `SWEEP_DIR = "../results/sweep_001"` and derive all paths from it.
2. Load `summary.json`; replace every mock value with a real computation from the streams.
3. Add the required figures: win-rate by variant, ablation effect, forfeit/quota-abort counts,
   best-of-N comparison, and the READ-accuracy correlation cell.
4. Run the notebook top-to-bottom so outputs are saved; export to `notebooks/analysis.html`
   (`uv run jupyter nbconvert --to html --execute notebooks/analysis.ipynb`).
**Verify:** notebook runs clean top-to-bottom; `analysis.html` exists and shows real numbers (no
`0.72`-style placeholders).
**Commit:** `feat(analysis): rewrite notebook on real sweep_001 data + export html`

---

## H3 — Expand `docs/PROMPTS.md` to ≥3 entries
**Goal:** The prompt log must document ≥3 real prompts (S-AC6 / FR-PL-2); today it has 1.
**Read first:**
- `docs/PROMPTS.md` (Entry 001 — and note it records a now-reversed Anthropic decision; add a
  correction line if it's misleading)
- `services/referee/brain/llm_brain.py`, `services/player/brain/player_prompts.py` (the actual prompts in use)
**Files (scope):** `docs/PROMPTS.md`.
**Do:** Add at least two more entries matching the existing entry's field format: the
referee-judge prompt and the PRO/CON player-brain prompt(s). Use the real prompt text/structure
from the code. Add a short note correcting Entry 001's stale "no gatekeeper / Anthropic" claim.
**Verify:** `docs/PROMPTS.md` has ≥3 entries; the new ones reflect code reality.
**Commit:** `docs(prompts): add referee + player prompt entries (>=3 total)`

---

## H4 — README: Troubleshooting + gatekeeper config + Examples
**Goal:** Close the three README gaps (FR-RM-3/4/5).
**Read first:**
- `README.md` (≈ line 86 "screenshots will be added"; ≈ 107 config block stops at `llm.model_name`)
- `config/setup.json` (the real `llm.gatekeeper` block) and `shared/api_gatekeeper.py` (error names)
**Files (scope):** `README.md` (+ reference images it points to, if you add any).
**Do:**
1. Add a **Troubleshooting** section covering 429 (rate limit), 503 (overloaded),
   `GatekeeperOpenError`, `GatekeeperExhaustedError`, and port-in-use.
2. Document the `llm.gatekeeper` config block (all fields + defaults) in the config section.
3. Replace the "screenshots will be added" placeholder with a real **Examples** section: a short
   transcript snippet and a figure from `analysis.html` (or a link to it).
**Verify:** grep README for `Troubleshoot`, `gatekeeper`, `429` → all present; no "will be added" left.
**Commit:** `docs(readme): add troubleshooting, gatekeeper config, and examples`

---

## H5 — Architecture diagram
**Goal:** Provide the architecture diagram the submission requires (S-AC8 / FR-AD-1..3).
**Read first:** `docs/ORCHESTRATION.md` and `docs/PLAN.md §1` (the architecture described in prose).
**Files (scope):** new `assets/architecture.mmd` (Mermaid source) + `assets/architecture.png` (rendered); reference it from `README.md` and `PLAN.md §1`.
**Do:** Author a Mermaid diagram showing referee, two players, transport, protocol, game engine,
brains, gatekeeper, and fault-tolerance threads. Render it to PNG (Mermaid CLI, or paste into a
renderer and export). Link the PNG from README and PLAN §1.
**Verify:** both `assets/architecture.mmd` and `assets/architecture.png` exist and are referenced.
**Commit:** `docs(assets): add architecture diagram and link from README/PLAN`

---

## H6 — Final submission gate
**Goal:** Prove the whole thing is green and take the submission snapshot.
**Read first:** `docs/CURRENT_STATE.md` (currently experiment-narrative form); `docs/devlog/` format.
**Files (scope):** new `docs/devlog/<today>-submission-gate.md`, rewrite `docs/CURRENT_STATE.md`.
**Do:**
1. Run the full gate (commands below). Everything must pass and coverage stay ≥85%.
2. Write `docs/devlog/<today>-submission-gate.md` pasting the pytest + ruff output and the current
   commit hash.
3. Rewrite `docs/CURRENT_STATE.md` as a one-screen **submission snapshot**: one line
   `Submission-ready snapshot taken at <commit> on <date>`, then a short bullet list of what ships
   (modules done, dataset = sweep_001, notebook = analysis.html, known limitations).
**Verify:**
```
uv run pytest -q
uv run ruff check src tests
```
Both clean; the two docs reflect reality.
**Commit:** `chore(submission): final gate green + submission snapshot`

---

### When H6 is `[x]` and pushed
Everything in `REMAINING_WORK.md` is closed. Tell the user the project is submission-ready and
point them at `docs/CURRENT_STATE.md`.
