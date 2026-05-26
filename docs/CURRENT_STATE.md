# Current Project State

Last updated: 2026-05-26

## Source Of Truth

Use this repo:

```text
C:\Users\Hp\OneDrive\Desktop\Semester6\ORCHISTRATION_AI\HW2\AI_ORCHESTRATION_HW2
```

Do not use the outer `HW2` repo as source of truth.

## Git State

Latest implementation commit:

```text
8a5c372 fix(player): include transcript and real evidence pack
```

There may be a newer docs-only handoff commit after this line. `8a5c372` is the last code/runtime
state described here.

Recent important commits:

```text
8a5c372 fix(player): include transcript and real evidence pack
55b8e13 fix(config): use current Gemini flash lite model
20ac986 feat(cli): run visible Gemini debates
241fa15 feat(player): complete arsenal and experiment harness
```

## Phase State

The project is no longer in feature-build mode. It is in experiment/run/report mode.

Completed:

- Referee/debate core: state, engine, matchmaking, game loop, results.
- Referee brains: simple referee and Gemini referee.
- Player arsenal P0-P7: prompts, output parser, selector, LLM brain, private capture, agent wiring.
- Experiment harness Module J: sweep runner, evidence pack, result streams, analysis notebook.
- User-facing CLIs: `uv run referee` and `uv run player`.

## Runtime Config

Current Gemini model:

```text
gemini-2.5-flash-lite
```

Current evidence pack:

```text
data/evidence_pack_primary.json
```

Local secret:

```text
.env
```

The `.env` file contains `GOOGLE_API_KEY`. Never open it, print it, or commit it.

## Last Verification

Last full gate:

```text
uv run pytest -q
272 passed
coverage 93.27%
```

Last lint:

```text
ruff check src tests
clean
```

Known warning:

```text
google.generativeai is deprecated; migrate to google.genai later.
```

## How To Run

Open three PowerShell terminals in the repo root.

Terminal 1, cheap/simple referee with real Gemini players:

```powershell
uv run referee --config config/setup.json --brain simple --move-timeout 120 --show-transcript
```

Terminal 2:

```powershell
uv run player --config config/setup.json --name PlayerA --brain llm
```

Terminal 3:

```powershell
uv run player --config config/setup.json --name PlayerB --brain llm
```

To run the real Gemini referee too, use this in Terminal 1:

```powershell
uv run referee --config config/setup.json --brain llm --move-timeout 120 --show-transcript
```

## Outputs

The referee terminal prints:

```text
=== Debate Transcript ===
...
=== Verdict ===
```

Generated files live under:

```text
results/
results/run_001/
```

These generated JSONL files are ignored by git.

## Gemini Quota Notes

If a player or referee fails with `429` and `limit: 0`, the API key is being accepted but the
Google AI Studio project has no quota for that model at that moment. This is not a repo bug.

Check:

```text
https://aistudio.google.com/rate-limit
```

Options are to wait for reset, use another Google Cloud project/API key, or enable billing.

## Next Useful Work

1. Run a clean match after commit `8a5c372`.
2. Inspect transcript quality and `results/` JSONL.
3. Run a small sweep only after quota is stable.
4. Use `notebooks/analysis.ipynb` for reporting.
5. Optional cleanup: migrate from `google.generativeai` to `google.genai`.
