# PART D — Player generation params

The prompt builder already returns `gen_params` (temperature, top_p, seed) but the LLM call
throws them away, so runs aren't reproducible. Reference: `REMAINING_WORK.md` §4.

---

## D1 — Thread temperature/top_p/seed into the LLM call
**Goal:** The seed and sampling params produced by `build_player_prompt` actually reach the
Gemini call, so generation is deterministic/configurable instead of env-only.
**Read first:**
- `src/agent_arena/services/player/brain/llm_brain.py` (≈ 37–112; line ~40 does `prompt_str, _ = build_player_prompt(...)` and discards `gen_params`)
- `src/agent_arena/services/player/brain/player_prompts.py` (≈ 50–145 — what `gen_params` contains)
- `src/agent_arena/shared/llm_client.py` (≈ 29–35 reads temp from env; ≈ 118–121 the `generate_text` / `GoogleGenAIClient` call building `GenerateContentConfig`)
**Files (scope):** `services/player/brain/llm_brain.py`, `shared/llm_client.py`.
**Do:**
1. In `llm_brain.py`, stop discarding `gen_params`: capture it and pass `temperature`, `top_p`,
   and `seed` into the LLM call.
2. In `llm_client.py`, give `generate_text` (and the `GoogleGenAIClient` backend) optional
   `temperature`, `top_p`, `seed` kwargs and forward them into `GenerateContentConfig`. Keep the
   env var as the fallback default only when the kwarg is `None`.
**Verify:**
```
uv run ruff check <files-you-changed>
uv run pytest tests/unit/services/player/brain/test_llm_brain.py tests/unit/shared/test_llm_client.py -q
```
Add/extend a test asserting the params from `gen_params` are forwarded into the client call
(mock the backend and assert it received the seed/temperature).
**Commit:** `fix(player): forward temperature/top_p/seed from prompt into the LLM call`

---

## D2 — Gate-guard test: player brain must not import the raw SDK
**Goal:** A test that fails if any player brain module imports `google.generativeai` /
`google.genai` directly or constructs a real client — all LLM access must go through `LLMClient`.
**Why:** `REMAINING_WORK.md` §4 (PL-AC3) — no such guard exists.
**Read first:**
- `src/agent_arena/services/player/brain/` (list the modules)
- any existing "no direct import" style test if present (search tests for `import` assertions)
**Files (scope):** new file `tests/unit/services/player/brain/test_no_direct_sdk.py` only.
**Do:** Write a test that imports each player brain module's source (or uses `ast`/`importlib`
inspection) and asserts none of them reference `google.generativeai` or `google.genai` at module
scope, and that they obtain LLM access only via `LLMClient`.
**Verify:**
```
uv run ruff check <files-you-changed>
uv run pytest tests/unit/services/player/brain/test_no_direct_sdk.py -q
```
**Commit:** `test(player): guard against direct Gemini SDK imports in brain modules`
