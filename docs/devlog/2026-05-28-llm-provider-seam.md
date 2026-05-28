# 2026-05-28 — LLM provider seam (google | gemini-cli)

## Why

The AI Studio free key caps `gemini-2.5-flash-lite` at **20 requests/day**, and one full
LLM-refereed match needs ~40 calls. That cap cannot be paced around (see
[`2026-05-26-first-live-llm-match.md`](2026-05-26-first-live-llm-match.md)). We needed a
second backend with a higher daily quota that still costs nothing.

**Gemini Code Assist for individuals** is the relevant option: it authenticates with a
personal Google account via OAuth (no billing) and grants ~60 RPM / 1000 RPD on Gemini
2.5 Pro. The official `gemini` CLI already implements that OAuth flow and caches creds
under `~/.gemini/`. Cheapest integration: shell out to the CLI.

We considered (and rejected): (a) hitting the `cloudcode-pa.googleapis.com` endpoint
directly with the cached OAuth token — works, but unofficial and brittle for an academic
artifact; (b) enabling billing on a GCP project and going through Vertex / paid AI Studio
— this is still the right call before the final Module J sweep, but requires a credit
card and is parked for now.

## What changed

**Code:** [`shared/llm_client.py`](../../src/agent_arena/shared/llm_client.py)

- Split into two backends behind a single interface:
  - `GoogleGenAIClient` — existing AI Studio key path, **unchanged behavior**.
  - `GeminiCLIClient` — subprocess to `gemini -m <model> -p <prompt>`, parses JSON from
    stdout (strips ` ```json ` fences, falls back to first-`{` / last-`}` extraction),
    reuses the existing `_backoff_seconds` for 429 / quota / unavailable retries.
- `LLMClient` is now a `__new__`-based façade:
  `LLMClient(provider="google" | "gemini-cli")`. Resolution order: explicit arg →
  `LLM_PROVIDER` env var (fallback) → `LLMError`. Existing callsites keep the same
  import and the same type annotation.

**Wiring:** the previously-ignored `LLMConfig.provider` field in
[`shared/config.py`](../../src/agent_arena/shared/config.py) is now actually consumed.

- [`services/player/agent.py:87`](../../src/agent_arena/services/player/agent.py) →
  `LLMClient(provider=self.config.llm.provider)`.
- [`services/referee/brain/llm_brain.py:53`](../../src/agent_arena/services/referee/brain/llm_brain.py)
  → `LLMRefereeBrain(model_name=..., provider=...)`. Defaults preserved
  (`provider="google"`) so test mocks `MockLLMRefereeBrain()` / `OfflineMockLLMRefereeBrain()`
  still instantiate with no args. **Trade-off:** a future production callsite that
  forgets to pass `provider` silently gets `"google"` instead of erroring loudly.
  Acceptable today; tighten before the final Module J sweep if we want stricter rigor.
- [`apps/run_helpers.py:18`](../../src/agent_arena/apps/run_helpers.py) and
  [`apps/sweep_runner.py:139`](../../src/agent_arena/apps/sweep_runner.py) thread
  `config.llm.provider` into `LLMRefereeBrain`.

## How to switch backends

Edit [`config/setup.json`](../../config/setup.json), `llm.provider`:

- `"google"` (default) → AI Studio free key via `GOOGLE_API_KEY` env var. 20 req/day cap.
- `"gemini-cli"` → official Gemini CLI subprocess. Prereqs:
  1. `npm install -g @google/gemini-cli`
  2. Run `gemini` once and complete the browser OAuth with your personal Google account.
     Creds cache under `~/.gemini/`.
  3. Bump `llm.model_name` to `gemini-2.5-pro` to get the 1000/day Code Assist quota
     (`flash-lite` runs there too but with the same low cap).

`LLM_PROVIDER` env var is kept as an ad-hoc override for one-off runs but is **not** the
source of truth — config is.

## Gotchas

- The CLI does not enforce schema server-side the way the SDK's `response_schema=` does.
  `GeminiCLIClient.generate_json` appends the JSON schema to the prompt and validates
  with Pydantic on receipt — expect occasional reprompts vs near-zero on the SDK path.
- Reproducibility caveat for the writeup: `gemini-cli` runs depend on a logged-in OAuth
  user. The professor cannot reproduce a `gemini-cli` run without their own login.
  AI Studio key runs remain the more portable option for the artifact.

## Gates

- `uv run pytest -q` → **225 passed**.
- No protocol diff. No new test hits the network (CLI backend is never invoked in tests;
  existing FakeLLMClient covers the seam).
