# 2026-05-28 — 503 storm silently turns a forfeit into a "win"

## What happened

Run 2 of the day was two terminals: `referee --brain llm --show-transcript` plus a
`player --name PlayerB --brain llm` (the PlayerA terminal also running off-screen).

The referee finished the match cleanly and printed a verdict:

```
=== Verdict ===
Winner: PRO
Margin: 0.15
Rationale: ... CON's evidence, while improving, did not quite match PRO's overall average.
```

PlayerB's terminal told a different story:

```
INFO:httpx:... gemini-2.5-flash:generateContent "HTTP/1.1 200 OK"
INFO:httpx:... gemini-2.5-flash:generateContent "HTTP/1.1 200 OK"
INFO:httpx:... gemini-2.5-flash:generateContent "HTTP/1.1 503 Service Unavailable"   # ×6
ERROR:agent_arena.services.player.agent:Player agent PlayerB exception:
  Failed after 6 attempts: 503 UNAVAILABLE. ...
    'message': 'This model is currently experiencing high demand. ...'
Player PlayerB finished
```

PlayerB hit a Gemini Flash capacity spike, exhausted its 6-attempt retry budget
inside ~30 s, and exited. The referee's `recv_timed` on PlayerB then expired at the
120 s `--move-timeout`, and
[`_turn_runner.py:104`](../../src/agent_arena/services/referee/_turn_runner.py)
applied the default move:

```python
if raw is None:
    return engine.apply_move(state, {"text": ""}, flag="timeout", retry_count=attempt)
```

…for every remaining CON turn. PRO continued submitting real arguments; the
judge scored a transcript where CON's later turns were empty strings, and
correctly concluded PRO had stronger evidence. From the verdict alone, the
margin looks legitimate.

## Why this matters

Two distinct problems converged:

1. **Player resilience too thin.** Six attempts with `2^attempt` backoff caps out
   at ~63 s. The 503 cluster we hit lasted longer than that, so the player died
   for a transient upstream condition. Run 1 (same day, same model) shows the
   referee itself rode through a 4-in-a-row 503 burst on its own LLM calls — pure
   luck the spike there was shorter.

2. **Forfeits are invisible in the verdict.** The per-turn `[referee flag] timeout`
   does appear in `--show-transcript`, but the verdict block at the end has no
   summary of how many turns were defaulted. A grader skimming the verdict (or
   any downstream sweep that records `winner` + `margin`) would treat this
   forfeit as a real PRO win with a 0.15 edge.

The combination is the bad outcome: capacity flakiness in the upstream API gets
laundered into a clean-looking debate result.

## Fix (separate commit)

- `shared/llm_client.py`: retry budget 6 → 10, max backoff 65 s → 120 s, ±25%
  jitter on backoff (so two players that 503 together don't sync their retry
  schedules), and 502/504 added to the retryable set.
- `apps/run_helpers.py`: `print_transcript` now prints a per-side forfeit count
  after the verdict, surfaces `terminated_reason` when the match was
  force-ended, and prints an explicit warning when the losing side defaulted
  more turns than the winner — the exact pattern from this incident.

Neither fix removes the underlying capacity issue; they widen the window we can
survive and make the failure mode loud when it does happen.
