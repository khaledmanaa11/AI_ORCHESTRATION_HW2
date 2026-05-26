# ORCHESTRATION — Session Control Panel

**Single source of truth for running this project across sessions.**
If you are an AI assistant starting a session here: READ THIS FILE FIRST, then run
`git log --oneline -8` and read `docs/TODO_referee.md`. Then report status and emit the next
developer prompt. **Never make the director re-explain context.**

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
| ▶ P2–P7 | **player-arsenal triplet** (prompts/parser/selector/llm-brain/capture/wiring) — see `PRD/PLAN/TODO_player.md` | `[ ]` | — |
| J | experiment sweep (resumable, throttled to Gemini free tier) + results JSONL + analysis notebook | `[ ]` | — |
| K | cross-cutting quality gates — asserted every phase | `[~]` | ongoing |

**Player-arsenal triplet — WRITTEN (2026-05-26):** `docs/PRD_player.md`, `docs/PLAN_player.md`,
`docs/TODO_player.md`. Build-shape locked: one structured Gemini call/turn (BS-1), deterministic
Best-of-N selector (BS-2), shared LLM client (BS-3), A+ seed reproducibility (BS-4), per-process
stream files + post-game dump (BS-5). Build order `P0→P7`; **resume at P0** (factor the Gemini
client to `shared/`). Module J (the sweep) consumes this triplet's stream-b output.

**Reference docs:** `docs/TODO_referee.md` (actionable spec), `docs/PRD_referee.md` (requirements),
`docs/PLAN_referee.md` (design), `docs/DESIGN_LEDGER.md` (rationale of record).

**Model provider:** Google Gemini via AI Studio **free** API key (`GOOGLE_API_KEY` env). Rate limits,
not cost, are the constraint for J. Tests are always offline (mock the client).
