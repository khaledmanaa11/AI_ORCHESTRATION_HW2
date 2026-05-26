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
f1cc665 fix(shared/llm-client): honor server retry-after on 429 backoff
```

Docs-only commits (devlog) sit on top of this. `f1cc665` is the last code/runtime state.

Recent important commits (2026-05-26 live-testing session):

```text
52a964d docs(devlog): append Round 4 finale
04ca9c4 docs(devlog): commit verbatim terminal captures
4611d97 docs(devlog): capture the first-live-LLM-match session
f1cc665 fix(shared/llm-client): honor server retry-after on 429 backoff
c990cd1 chore(config,docs): set locked primary motion; refresh roadmap
94106f7 fix(shared/llm-client): migrate to google.genai SDK
```

The full story of this session (the referee schema crash, the SDK migration, both quota
walls, and the fixes) is in `docs/devlog/2026-05-26-first-live-llm-match.md` with verbatim
terminal captures under `docs/devlog/captures/`.

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

Last full gate (after the google.genai migration + backoff fix):

```text
uv run pytest -q
272 passed
coverage 94.19%
```

Last lint:

```text
ruff check src tests
clean
```

Known warnings: none. The `google.generativeai` deprecation warning is GONE — the client
was migrated to `google.genai` (commit 94106f7).

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

## Gemini Quota Notes (MEASURED 2026-05-26 — this is the real blocker)

`gemini-2.5-flash-lite` free tier enforces TWO caps simultaneously:

```text
10 requests / MINUTE  (GenerateRequestsPerMinutePerProjectPerModel-FreeTier)
20 requests / DAY     (GenerateRequestsPerDayPerProjectPerModel-FreeTier)
```

- The **per-minute** cap is now handled in code: `llm_client.py` parses the server's
  `retry in Xs` and sleeps that long (commit f1cc665). A `429` burst no longer aborts a match.
- The **per-day** cap CANNOT be paced around. One full LLM-referee match needs ~40 calls
  (10 player moves x best_of_N=3 + per-turn referee evals + verdict), so the 20/day cap
  cannot fund even a single full match. On 2026-05-26 we exhausted two separate keys' daily
  allowances and never completed a clean 10-turn debate.

Check usage: `https://aistudio.google.com/rate-limit`

## Next Useful Work

1. **Pick a quota path to finish a match** (the only real blocker):
   - cheapest: `debate.player.best_of_N` -> 1 and use `--brain simple` referee (~10 calls/match);
   - real fix: enable billing on a Google project (also the only way Module J's 250-400-match
     sweep can ever run);
   - or use a model with a higher daily free cap.
2. Run a clean match on the latest code (`f1cc665`) once quota allows.
3. Inspect transcript quality and `results/` JSONL.
4. Use `notebooks/analysis.ipynb` for reporting.
5. Context for whatever happened: read `docs/devlog/2026-05-26-first-live-llm-match.md`.
