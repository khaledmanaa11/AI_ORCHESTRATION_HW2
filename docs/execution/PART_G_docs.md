# PART G — Docs & process reconciliation

These steps are **documentation only** — no source-code behavior changes. Verify = "the file
exists and says the right thing" + `ruff` still clean (docs don't affect it, but run it anyway).
Reference: `REMAINING_WORK.md` §7, §8, §9, §10.

> **Decision already made (do not re-litigate):** the implementation uses **Google Gemini**, and
> that is the intended path for this homework. So wherever PRD/PLAN say "Anthropic SDK /
> `ANTHROPIC_API_KEY`", the **docs** get updated to match the **code** (Gemini / `GOOGLE_API_KEY`).
> Never rewrite the code to Anthropic.

---

## G1 — Reconcile Anthropic→Gemini in PRD.md + PLAN.md
**Read first:**
- `docs/PRD.md` (§3.4, FR-L1–L3) and `docs/PLAN.md` (§8) — the Anthropic references
- `src/agent_arena/shared/llm_client.py` (the real Gemini wiring, for accurate wording)
**Files (scope):** `docs/PRD.md`, `docs/PLAN.md`.
**Do:** Replace every "Anthropic SDK / `anthropic` / `ANTHROPIC_API_KEY` / Claude model" mention
in those two files with the Gemini equivalent (`google-genai`, `GOOGLE_API_KEY`, the configured
Gemini model). Add a one-line note: "LLM backend changed from Anthropic to Google Gemini on
2026-05-28; see `docs/gemini_paid_tier` decision." Don't touch unrelated text.
**Verify:** grep both files for `anthropic`/`ANTHROPIC` (case-insensitive) → 0 hits.
**Commit:** `docs: reconcile PRD/PLAN to Gemini backend (was Anthropic)`

---

## G2 — Write `docs/PRD_referee_brain.md`
**Read first:**
- `src/agent_arena/services/referee/brain/` (base.py, simple_brain.py, llm_brain.py)
- a sibling PRD for format, e.g. `docs/PRD_player.md`
**Files (scope):** new `docs/PRD_referee_brain.md`.
**Do:** Write the missing per-mechanism PRD describing the referee brain: the `RefereeBrain` ABC,
`SimpleRefereeBrain` (deterministic scoring), `LLMRefereeBrain` (3-arm judging + grounding),
inputs/outputs (`RefereeContext`/`RefereeDecision`), and acceptance criteria. Match the structure
and heading style of the existing per-mechanism PRDs.
**Verify:** file exists; sections match the sibling PRD's shape.
**Commit:** `docs: add PRD_referee_brain.md (was missing)`

---

## G3 — Write `PLAN_protocol.md` + `TODO_protocol.md`
**Read first:** `docs/PRD_protocol.md`; a sibling pair e.g. `PLAN_network.md` + `TODO_network.md` for format.
**Files (scope):** new `docs/PLAN_protocol.md`, new `docs/TODO_protocol.md`.
**Do:** Draft the PLAN (build order mapping each PRD requirement to its implementing file) and the
TODO (checkbox tasks). Mark already-implemented items `[x]` with their `file:line` evidence (see
`REMAINING_WORK.md` §10 "Done"); leave the real gaps `[ ]` (e.g. `ErrorCode` enum, post-handshake
timeouts — note these are covered by steps A1/F5).
**Verify:** both files exist and reference real paths.
**Commit:** `docs: add PLAN_protocol.md and TODO_protocol.md (orphan PRD)`

---

## G4 — Write `PLAN_matchmaking.md` + `TODO_matchmaking.md`; fix PRD roles
**Read first:** `docs/PRD_matchmaking.md`; `src/agent_arena/services/referee/matchmaking.py` (roles are `PRO`/`CON`).
**Files (scope):** new `docs/PLAN_matchmaking.md`, new `docs/TODO_matchmaking.md`, edit `docs/PRD_matchmaking.md`.
**Do:**
1. In `PRD_matchmaking.md`, replace `PLAYER_1`/`PLAYER_2`/`X`/`O` role language with `PRO`/`CON`
   to match the code.
2. Write the PLAN + TODO as in G3, marking done vs open per `REMAINING_WORK.md` §9 (open items:
   validate-on-REGISTER → A1, ERROR-before-close → A2, pre-registration disconnect timeout).
**Verify:** all three files consistent; PRD has no `PLAYER_1`/`X`/`O` left.
**Commit:** `docs: add matchmaking PLAN/TODO and fix PRD roles to PRO/CON`

---

## G5 — Write `PLAN_game_engine.md` + `TODO_game_engine.md`; reconcile signatures
**Read first:** `docs/PRD_game_engine.md`; `src/agent_arena/services/game/engine_base.py` + `debate_engine.py`.
**Files (scope):** new `docs/PLAN_game_engine.md`, new `docs/TODO_game_engine.md`, edit `docs/PRD_game_engine.md`.
**Do:**
1. The engine works and is tested; the PRD's method names/signatures are stale. Update
   `PRD_game_engine.md` so `check_terminal` → `is_terminal`, and note that `role` enforcement
   lives in `_turn_runner` (routing), not in `validate_move`/`apply_move`. (Reconcile **PRD to
   code**, since the code is the tested truth — do **not** change the engine.)
2. Write the PLAN + TODO mapping each requirement to its implementing `file:line`
   (`REMAINING_WORK.md` §8), leaving "deterministic replay" as an open `[ ]` if still absent.
**Verify:** three files consistent; PRD signatures match `engine_base.py`.
**Commit:** `docs: add game_engine PLAN/TODO and reconcile PRD to engine signatures`

---

## G6 — Fix stale statuses in `docs/TODO.md`
**Read first:** `docs/TODO.md` (T4.2, T4.4 notes), and confirm against code:
`services/referee/matchmaking.py` (complete), `services/game/debate_engine.py` (the chosen engine).
**Files (scope):** `docs/TODO.md`.
**Do:** Mark `T4.4` (matchmaking) `[x]` — it's implemented. Update the `T4.2 trivial_game.py`
note to reflect that `DebateEngine` replaced it. Fix any other status that `REMAINING_WORK.md` §7
flagged as stale. Don't invent new tasks here.
**Verify:** statuses match reality; no checkbox claims something the code doesn't have.
**Commit:** `docs(todo): correct stale top-level task statuses`
