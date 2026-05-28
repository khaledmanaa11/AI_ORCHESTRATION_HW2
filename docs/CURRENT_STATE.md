# Current Project State

Last updated: 2026-05-28

## Source Of Truth

Use this repo:

```text
C:\Users\Hp\OneDrive\Desktop\Semester6\ORCHISTRATION_AI\HW2\AI_ORCHESTRATION_HW2
```

Do not use the outer `HW2` repo as source of truth.

## Git State

Latest implementation commit:

```text
04540b1 feat(shared/llm-client): provider seam (google | gemini-cli), config-driven
```

Uncommitted (intentional, for paid-tier run):

```text
config/setup.json:
  llm.model_name        gemini-2.5-flash-lite -> gemini-2.5-flash
  debate.player.best_of_N  1 -> 3
```

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
gemini-2.5-flash   (paid tier, billing enabled 2026-05-28)
```

Provider seam (from commit 04540b1): `llm.provider` in `config/setup.json` selects
between `"google"` (direct google.genai SDK, default) and `"gemini-cli"` (local
shim). Paid runs use `"google"`.

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

## Gemini Quota (RESOLVED 2026-05-28)

Billing is enabled on the Google Cloud project behind `GOOGLE_API_KEY`. The previous
free-tier caps (10 RPM / 20 RPD on `gemini-2.5-flash-lite`) that blocked us on
2026-05-26 no longer apply. Same `.env` key, paid quota now.

Paid-tier limits on `gemini-2.5-flash` (Tier 1): 1,000 RPM / 10,000 RPD — comfortably
covers a full Module J 250-400 match sweep.

Existing 429 backoff in `llm_client.py` (commit f1cc665) is still in place as a safety net.

Check usage / spend:
- Rate limits: https://aistudio.google.com/rate-limit
- Billing/budget: Google Cloud Console -> Billing -> Budgets & alerts

A $15 budget alert is configured on the GCP project as a guardrail.

## How To Run (paid tier, current config)

Three PowerShell terminals at repo root.

Terminal 1, full LLM referee + LLM players (the real configuration):

```powershell
uv run referee --config config/setup.json --brain llm --move-timeout 120 --show-transcript
```

Terminal 2:

```powershell
uv run player --config config/setup.json --name PlayerA --brain llm
```

Terminal 3:

```powershell
uv run player --config config/setup.json --name PlayerB --brain llm
```

Cheaper sanity variant: swap Terminal 1 to `--brain simple` (simple referee, real
LLM players) — ~10 calls/match instead of ~40.

## First Clean End-to-End Match (2026-05-28)

First fully successful LLM-vs-LLM-vs-LLM match completed on the paid tier.

```text
Match ID: a308b937-33a5-4599-8c24-f2d1b33d90e4
Motion:   Autonomous AI agents should be allowed to make consequential decisions
          without human approval
Result:   CON wins, margin -0.22
Turns:    10 (5 PRO / 5 CON, opening/rebuttal/closing structure correct)
Calls:    ~12 Gemini calls; one 503 auto-retried into 200; no quota errors
```

Artifacts:

```text
results/a308b937-33a5-4599-8c24-f2d1b33d90e4_trajectory.jsonl   (10 lines, referee trace)
results/run_001/a308b937-...player_PRO.jsonl                    (5 lines, PRO private capture)
results/run_001/a308b937-...player_CON.jsonl                    (5 lines, CON private capture)
```

Verdict rationale is coherent — identifies accountability-as-prerequisite vs.
accountability-in-parallel as the actual crux. Players cite DOC-IDs from the
evidence pack. CON's margin is non-degenerate (not a landslide), suggesting
rubric weighting works.

## Known Minor Bug

`[referee tell]` per-turn text occasionally mislabels which side just spoke
(observed at turns 07 and 08 of the 2026-05-28 match: PRO turn labeled as
"CON presented its rebuttal" and vice versa). The `tell` is human-readable
flavor text; it does NOT feed the verdict path. Worth investigating but not
blocking. Likely a label-swap somewhere in the referee's turn-summary prompt
or post-processing.

## Next Useful Work

1. Commit the `config/setup.json` change (`gemini-2.5-flash`, `best_of_N=3`)
   plus the CURRENT_STATE update — this is the new known-good baseline.
2. Run 2-3 more matches to confirm stability and gather variance data.
3. Investigate the `[referee tell]` side-label bug (see "Known Minor Bug").
4. Launch the Module J sweep when ready (250-400 matches). Estimated cost
   ~$5-15 against the $15 GCP budget alert; consider raising the budget if
   you plan to run the full sweep more than once.
5. Use `notebooks/analysis.ipynb` for the writeup.
6. Historical context for the quota saga (now resolved):
   `docs/devlog/2026-05-26-first-live-llm-match.md`.
