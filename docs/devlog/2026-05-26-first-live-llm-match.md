# Devlog — 2026-05-26: First live LLM debate match (bring-up & bug hunt)

> This is a play-by-play of the session where we tried to run the *first real*
> LLM-vs-LLM debate with a live Gemini referee. It is written so a reader can feel
> like they were sitting next to us: every bug, every error message, every fix, in
> the order it happened. Raw terminal captures live in [`captures/`](captures/).

**Roles:** director (Khaled) + orchestrator (Claude). The whole build (Modules A–J,
player arsenal, CLIs) was already done and green going in. This session was pure
**run / test / debug** — the first time the real referee brain met real players over
the wire.

**Run recipe (3 terminals):**
```powershell
uv run referee --config config/setup.json --brain llm --move-timeout 120 --show-transcript
uv run player  --config config/setup.json --name PlayerA --brain llm
uv run player  --config config/setup.json --name PlayerB --brain llm
```

---

## Round 1 — the referee crashes on turn 1  💥

We launched the full LLM match and the referee aborted almost immediately. Full log:
[`captures/run1-referee-schema-crash.log`](captures/run1-referee-schema-crash.log).

```
ValueError: Protocol message Schema has no "maximum" field.
...
agent_arena.shared.llm_client.LLMError: Unexpected error during generation:
    Unknown field for Schema: maximum

=== Verdict ===
Winner: null
Margin: 0.0
Rationale: The debate concluded in a draw ...
```

**Diagnosis.** The referee's score model declares bounded fields:

```python
# services/referee/brain/llm_brain.py
class TurnEvaluationResult(BaseModel):
    logic_score: float = Field(ge=0, le=10)
    evidence_score: float = Field(ge=0, le=10)
    rebuttal_score: float = Field(ge=0, le=10)
    persuasion_score: float = Field(ge=0, le=10)
```

Pydantic compiles `ge`/`le` into JSON-schema `minimum`/`maximum`. The code passed that
schema straight to the **deprecated `google.generativeai`** SDK, whose proto `Schema`
has **no `maximum` field** → it threw on *every* referee `EVALUATE_TURN` call.

**Two silver linings already visible here:**
- The **players worked** — PlayerA generated a real move against live Gemini before the
  referee choked (the player output schema has no numeric bounds, so it was unaffected).
- The **verdict-reachability invariant held**: even on a mid-loop crash, the `try/finally`
  still produced exactly one `GAME_OVER` (a degenerate draw). That's the 8.6 guard doing
  its job.

**Decision:** rather than patch around the old SDK, do the proper fix the docs had already
flagged — migrate to `google.genai`, which supports `min`/`max` natively *and* clears the
deprecation warning.

→ **commit `94106f7`** — `fix(shared/llm-client): migrate to google.genai SDK`
Gate after: `ruff` clean, **272 passed**, coverage **93.39%**, protocol diff empty.
The public `LLMClient` method signatures were kept identical, so referee + player call
sites and all mocked tests were untouched.

---

## Round 2 — schema fixed, then the *daily* quota wall  🧱

Re-ran the same match. The migration **worked** — full log:
[`captures/run2-referee-daily-quota.log`](captures/run2-referee-daily-quota.log).

```
INFO:httpx:HTTP Request: POST .../gemini-2.5-flash-lite:generateContent "HTTP/1.1 200 OK"
INFO:httpx:HTTP Request: POST .../gemini-2.5-flash-lite:generateContent "HTTP/1.1 200 OK"
INFO:httpx:HTTP Request: POST .../gemini-2.5-flash-lite:generateContent "HTTP/1.1 200 OK"
INFO:httpx:HTTP Request: POST .../gemini-2.5-flash-lite:generateContent "HTTP/1.1 429 Too Many Requests"
```

`200 OK` — the referee was actually judging turns, and the deprecation banner was gone.
But then **429s**, and the reason was sobering:

```
limit: 20, model: gemini-2.5-flash-lite
quotaId: GenerateRequestsPerDayPerProjectPerModel-FreeTier   <-- 20 requests PER DAY
```

The free tier on this model is **20 requests per day**, far lower than we'd assumed
(~1500/day). A single full LLM-referee match (≈ 40 calls with Best-of-N=3) can exhaust
the entire day. Verdict came back forced: **CON, margin -1.175**.

**Side quest while waiting on quota — two flagged cleanups:**
- The config motion was the placeholder `"AI is beneficial"`. The evidence pack
  (`data/evidence_pack_primary.json`) is clearly built for the *locked* motion — its docs
  split cleanly PRO (speed, cost, diagnostics, grid) vs CON (bias, flash crash,
  accountability, weapons, hallucinations). Swapped it to the real motion.
- The ROADMAP table in `docs/ORCHESTRATION.md` still showed P2–P7 and J as "not started"
  even though everything was done & pushed. Refreshed it to **run/report mode** with real
  commit hashes.

→ **commit `c990cd1`** — `chore(config,docs): set locked primary motion; refresh roadmap to run mode`

---

## Round 3 — new key, now the *per-minute* wall  ⏱️

Khaled dropped a fresh API key into `.env`. Re-ran. Full log:
[`captures/run3-referee-rpm-quota.log`](captures/run3-referee-rpm-quota.log).

Five `200 OK`s this time — **and the verdict header now shows the real motion**:

```
Motion: Autonomous AI agents should be allowed to make consequential decisions without human approval
```

Then 429 again, but a *different* quota:

```
limit: 10, model: gemini-2.5-flash-lite
quotaId: GenerateRequestsPerMinutePerProjectPerModel-FreeTier   <-- 10 requests PER MINUTE
Please retry in 22.212969542s.
```

This key had daily quota left — the problem was **requests-per-minute (10/min)**.
Best-of-N=3 makes calls bursty, so we blew the minute window fast. The server politely
asked us to **wait ~22s**, but our backoff slept only 1–2s before giving up → abort.
Verdict: **CON, margin -0.7958**.

**Fix:** make the 429 backoff honor the server's suggested `retry in Xs` instead of a
fixed 1–2s, allow more attempts, and (bonus) factor the duplicated retry loop in
`generate_json`/`generate_text` into a single `_generate` helper:

```python
_RETRY_DELAY_RE = re.compile(r"retry in (\d+(?:\.\d+)?)s")

def _backoff_seconds(exc, attempt):
    match = _RETRY_DELAY_RE.search(str(exc))
    if match:
        return min(float(match.group(1)) + 1.0, _MAX_BACKOFF_SECONDS)
    return min(2.0 ** attempt, _MAX_BACKOFF_SECONDS)
```

→ **commit `f1cc665`** — `fix(shared/llm-client): honor server retry-after on 429 backoff`
Gate after: `ruff` clean, **272 passed**, coverage **94.19%**.

---

## Round 4 — the real run, throttled but patient  🐢

Re-ran with `--move-timeout 300` (so a turn can absorb the ~22s throttle waits). The
backoff now waits out each per-minute window instead of aborting. This run is slow by
design — at 10 calls/min with ~40 calls, a single match takes several minutes.

_(Result appended below once the match completes — see
[`captures/run4-referee-final.log`](captures/run4-referee-final.log).)_

<!-- RUN4_RESULT -->

---

## Commit timeline (this session)

| Commit | What |
|--------|------|
| `94106f7` | migrate `google.generativeai` → `google.genai` (fixes the `maximum`-schema referee crash) |
| `c990cd1` | set locked primary motion in config; refresh ORCHESTRATION roadmap to run mode |
| `f1cc665` | honor server retry-after on 429 backoff (fixes per-minute-quota aborts) |
| _(this doc)_ | devlog + raw terminal captures of the whole session |

## What we learned

1. **The substrate is sound.** The TCP loop, matchmaking, player arsenal, and the
   verdict-reachability invariant all behaved correctly even under two different crashes.
   Every failure still produced exactly one `GAME_OVER`.
2. **The deprecated SDK was a latent landmine.** Bounded Pydantic fields are common; the
   old SDK silently couldn't express them. `google.genai` removes that whole class of bug.
3. **Gemini free tier is the real constraint — and it has *two* limits.** ~20 requests/day
   *and* 10 requests/minute on `gemini-2.5-flash-lite`. Code can pace around the per-minute
   cap (we now do); only billing or a different model class clears the per-day cap. The
   Module J sweep (250–400 matches) is **infeasible on the free tier** as-is.
4. **Best-of-N multiplies API pressure.** N=3 triples player calls. For low-quota runs,
   dropping to N=1 roughly halves total calls per match.
