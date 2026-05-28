# ORCHESTRATION — Session Control Panel

**Single source of truth for running this project across sessions.**
If you are an AI assistant starting a session here: READ THIS FILE FIRST, then run
`git log --oneline -8` and read `docs/TODO_referee.md`. Then report status and emit the next
developer prompt. **Never make the director re-explain context.**

---

## Current handoff (2026-05-28)

**Active repo:** `C:\Users\Hp\OneDrive\Desktop\Semester6\ORCHISTRATION_AI\HW2\AI_ORCHESTRATION_HW2`.
Do not use the outer `HW2` repo as source of truth.

**Detailed fresh-session handoff:** read `docs/CURRENT_STATE.md` and the latest devlog under
`docs/devlog/` (most recent: `2026-05-28-llm-provider-seam.md`).

**2026-05-28 — LLM provider seam landed.** `shared/llm_client.py` now dispatches between
`GoogleGenAIClient` (AI Studio key, default) and `GeminiCLIClient` (subprocess to the official
`gemini` CLI, OAuth via personal Google account, ~60 RPM / 1000 RPD on Gemini 2.5 Pro). Selection
is driven by `llm.provider` in `config/setup.json` and threaded through
`LLMRefereeBrain(provider=...)` and `LLMClient(provider=...)` at both production callsites
(`apps/run_helpers.py`, `apps/sweep_runner.py`, `services/player/agent.py`). `LLM_PROVIDER` env
var is kept only as an ad-hoc override. Full rationale + switch-instructions in
`docs/devlog/2026-05-28-llm-provider-seam.md`. **Tests: 225 passed.** Not yet committed at the
time of this handoff write — orchestrator should commit before pushing.

**Latest implementation commit (before today's seam):** `f1cc665 fix(shared/llm-client): honor
server retry-after on 429 backoff`. Docs-only devlog commits (up to `52a964d`) sit on top.

**Project state:** the build phases are complete and we are in **experiment/run/report mode**.
Referee/debate core, both referee brains, player arsenal P0-P7, and Module J are all done. As of
the 2026-05-26 live-testing session the LLM path is FIXED and runnable — see below.

**2026-05-26 live-testing session (full play-by-play: `docs/devlog/2026-05-26-first-live-llm-match.md`):**
- `94106f7` migrated the LLM client from the deprecated `google.generativeai` to `google.genai` —
  the old proto Schema rejected the `maximum` field Pydantic emits for the referee's
  `Field(ge=0, le=10)` scores, crashing every LLM referee evaluation. Fixed + deprecation warning gone.
- `c990cd1` set the config motion to the locked primary motion (was placeholder "AI is beneficial")
  and refreshed the roadmap table to run mode.
- `f1cc665` made the 429 backoff honor the server's `retry in Xs` (was a too-short 1-2s), so the
  referee now recovers from per-minute rate-limit bursts instead of aborting.

**THE blocker is Gemini free-tier quota, not code:** `gemini-2.5-flash-lite` enforces 10 req/MINUTE
AND 20 req/DAY. Code now paces around the per-minute cap; the per-day cap cannot be paced and is too
small to fund one full match (~40 calls). To finish a match: `best_of_N`->1 + `--brain simple`, or
enable billing, or a higher-daily-cap model. See CURRENT_STATE.md "Gemini Quota Notes".

**Last verified gates:** `uv run pytest -q` -> `272 passed`, coverage `94.19%`.
`ruff check src tests` -> clean. No warnings (deprecation removed).

**Secrets:** `.env` exists locally with `GOOGLE_API_KEY`; never open it or print it. It is ignored by
git.

**Run a visible real-player match with cheap/simple referee:**

```powershell
uv run referee --config config/setup.json --brain simple --move-timeout 120 --show-transcript
uv run player --config config/setup.json --name PlayerA --brain llm
uv run player --config config/setup.json --name PlayerB --brain llm
```

**Run with real Gemini referee too:**

```powershell
uv run referee --config config/setup.json --brain llm --move-timeout 120 --show-transcript
uv run player --config config/setup.json --name PlayerA --brain llm
uv run player --config config/setup.json --name PlayerB --brain llm
```

If Gemini returns `429` with `limit: 0`, it is an AI Studio project quota issue, not a repo bug.
Check `https://aistudio.google.com/rate-limit`, wait for reset, use a different project, or enable
billing if desired.

Generated match files live under `results/` and are ignored by git.

---

## Roles

- **Director (Khaled):** says *"next phase"*. Hands prompts to the developer, pastes the
  developer's commit hash back. Decides scope.
- **Orchestrator (the chat assistant, e.g. this session):** reads state → writes the next
  developer prompt → after the developer commits, verifies the work → pushes if it passes.
- **Developer (a separate custom AI):** receives ONE self-contained prompt, implements ONE small
  phase, commits locally **(NO push)**, reports the commit hash + gate results.

---

## The session loop

1. **Director:** "next phase" (or names a specific phase).
2. **Orchestrator:** read this file + `git log` + `docs/TODO_referee.md` → state where we are →
   emit the next developer prompt using the TEMPLATE below.
3. **Director** hands the prompt to the developer; developer commits locally, returns the hash.
4. **Orchestrator:** run the VERIFICATION GATE on that commit → report PASS/FAIL + a short
   substance review (did it actually do the work, or stub it?).
5. **If PASS:** orchestrator runs `git push origin master`, then updates the ROADMAP below
   (tick the row, record the commit hash, move the ▶ RESUME pointer).
   **If FAIL:** orchestrator writes a fix-up prompt → back to step 3.

---

## Developer-prompt TEMPLATE (fill the {braces}, keep it lean)

```
Repo: C:\Users\Hp\OneDrive\Desktop\Semester6\ORCHISTRATION_AI\HW2\AI_ORCHESTRATION_HW2
Python/uv project. Do {PHASE NAME} ONLY. Prior phases committed & green.

GOAL: {one or two sentences}

READ ONLY THESE (don't grep the whole tree):
- docs/TODO_referee.md → {relevant section} only
- {exact source files the developer needs}

DO:
1. {atomic step}
2. {atomic step}
...

HARD CONSTRAINTS:
- Do NOT edit src/agent_arena/services/protocol/. PROTOCOL_VERSION stays "1.00" (R-AC9).
- No real network/API calls in tests — always inject a fake/stub (offline + free).
- No hardcoded host/port/timeout/weight/cap/model — all from config/env. No magic strings (constants.py).
- Every new source file <=150 code lines; split if needed.

GATE (must all pass):
  uv run ruff check src tests
  uv run pytest -q                                      # 0 failures
  uv run pytest --cov                                   # >=85%
  git diff --stat src/agent_arena/services/protocol/    # empty

THEN: tick the matching boxes + build-order row in docs/TODO_referee.md; update the top handoff
block to point at the next phase. Commit (NO push), stage only touched files:
  {type(scope): message}

  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>

REPORT: commit hash, "X passed", coverage %, confirm protocol diff empty, confirm no test hits network.
```

---

## Verification GATE (orchestrator runs these on the returned commit)

```
uv run pytest -q                                     # 0 failures
uv run ruff check src tests                          # clean
uv run pytest --cov                                  # >=85%
git diff --stat src/agent_arena/services/protocol/   # empty (R-AC9 / PROTOCOL_VERSION "1.00")
```
Plus a manual substance pass: read the changed files, confirm every source file <=150 code lines,
confirm no test imports `google.generativeai` or constructs a real client, and confirm the code
actually implements the phase (not a stub that just makes the gate green).

---

## Push policy

The developer **never** pushes. The orchestrator pushes **only after the gate passes**.
One logical phase per commit. Push command: `git push origin master`.

---

## ROADMAP (live — update after each push)

> Status: `[x]` done & pushed · `[~]` in progress · `[ ]` not started · `▶` = RESUME here

| Phase | What | Status | Commit |
|-------|------|--------|--------|
| A–F | game state, engine, brain base, simple brain, game loop, match setup | `[x]` | …→de73d5c |
| G | config/debate block + validation | `[x]` | 7dafdf8 |
| H | integration gate (real engine+brain → reproducible GAME_OVER) | `[x]` | 0e9434a |
| I | Gemini `LLMRefereeBrain` (swap-only) | `[x]` | e9cc7f8 |
| I.5 | **judge-prompt hardening** (3 arms carry rubric/motion/transcript; arms differ substantively) | `[x]` | 0053d55 |
| P0 | player-arsenal: factor Gemini client to `shared/llm_client.py` (referee+player reuse) | `[x]` | 319c451 |
| P1 | player-brain contract (`PlayerBrain` ABC + `PlayerContext`/`PlayerDecision`; seeded conformance) | `[x]` | 6dba9c1 |
| P2 | player prompts: ablation-aware structured prompt builder + fixture pack | `[x]` | deb4d60 |
| P3–P7 | player arsenal complete (parser/selector/llm-brain/capture/wiring) | `[x]` | 241fa15 |
| J | experiment sweep + results JSONL + analysis notebook | `[x]` | 241fa15 |
| CLI | `uv run referee` / `uv run player` runnable, `--show-transcript` | `[x]` | 20ac986 |
| fixes | flash-lite model default; player transcript + real evidence pack | `[x]` | 55b8e13, 8a5c372 |
| SDK | migrate `google.generativeai` → `google.genai` (fixes referee schema crash) | `[x]` | 94106f7 |
| K | cross-cutting quality gates — asserted every phase | `[x]` | ongoing |
| ▶ RUN | **experiment / run / report mode** — all build phases complete | `[~]` | — |

**BUILD COMPLETE (2026-05-26).** Every phase A→J plus the player-arsenal triplet, CLIs, and the
`google.genai` migration are committed and pushed. We are now in **run/report mode**, not
feature-build mode. The only thing gating real LLM matches is **Gemini free-tier quota**
(`gemini-2.5-flash-lite` = ~20 requests/day), not code. See `docs/CURRENT_STATE.md` for the
run recipe. `notebooks/analysis.ipynb` is the reporting surface once a sweep has data.

**Reference docs:** `docs/TODO_referee.md` (actionable spec), `docs/PRD_referee.md` (requirements),
`docs/PLAN_referee.md` (design), `docs/DESIGN_LEDGER.md` (rationale of record).

**Model provider:** dispatched by `llm.provider` in `config/setup.json`. Two backends:
- `"google"` (default) → AI Studio key (`GOOGLE_API_KEY` env). 20 req/day on `flash-lite`.
- `"gemini-cli"` → subprocess to `gemini` CLI (`npm i -g @google/gemini-cli` + one-time `gemini`
  OAuth). ~1000 req/day on `gemini-2.5-pro` via Code Assist for individuals.

Rate limits, not cost, are the constraint for J. Tests are always offline (mock the client).
The `gemini-cli` path is not portable for the professor's reproduction — keep AI Studio key as the
artifact-canonical backend, use `gemini-cli` for local sweeps.
