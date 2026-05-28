# 2026-05-28 — Run 3: forfeit surfaced loudly, but a 503 burst still cost a turn

## What happened

Third run of the day, single terminal:

```
uv run referee --config config/setup.json --brain llm --move-timeout 120 --show-transcript
```

Both players connected, match ran to completion. The httpx log shows two
503 clusters from `gemini-2.5-flash:generateContent`:

- **First cluster** (mid-match): 2 consecutive 503s, then recovered.
- **Second cluster** (just before turn 7): **4 consecutive 503s**, then 200s
  resumed.

Turn 7 (PRO REBUTTAL) came back as **0 words** with `[referee flag] timeout`.
Every other turn ran normally. Final verdict:

```
=== Verdict ===
Winner: CON
Margin: -2.775
...
[!] Forfeited turns — PRO: 1, CON: 0. Verdict reflects a partial debate; treat margin with caution.
[!] Losing side (PRO) defaulted more turns than the winner — the result is likely a forfeit, not a genuine outcome.
```

## What this tells us

### The fix from `eab4b2b` works

The forfeit-surfacing change is doing exactly what it was designed to do.
Without it, this would have printed a clean `Winner: CON, Margin: -2.775`
with no hint that PRO had a defaulted turn — the same silent-forfeit pattern
as Run 2, just with the sides swapped. Now both the per-side forfeit count
and the explicit "likely a forfeit, not a genuine outcome" warning fire.

### The underlying resilience is still marginal

The retry budget was widened to 10 attempts with ±25% jitter and 120 s cap.
That survived the **2-in-a-row** cluster earlier in the match. It did **not**
survive the **4-in-a-row** cluster before turn 7 — combined with the 120 s
move-timeout on the referee side, the player's retry chain blew past the
referee's patience and the turn defaulted.

Two observations:

1. The 4-burst is right at the edge of what 10 attempts with exponential
   backoff can absorb within a 120 s window. With ±25% jitter the actual
   wall time per cluster varies a lot run-to-run; we got unlucky here.
2. The referee's `--move-timeout 120` is the binding constraint, not the
   player's retry budget. Even if the player eventually recovers, if it
   takes >120 s the referee has already defaulted the turn.

## Not fixing yet

The visibility fix is the important one — a forfeit that's announced is a
debuggable forfeit. Bumping `--move-timeout` to e.g. 180 s would absorb
this specific burst but it's a knob, not a real fix; the right next step is
either (a) longer move-timeout as a config default for `llm` brain runs, or
(b) a per-turn "still alive, retrying upstream" heartbeat so the referee
knows to wait rather than default. Logging this for now; not changing code.

## Artifacts

- Verdict: CON wins, margin -2.775, **partial-debate warning fired**.
- Forfeits: PRO 1, CON 0.
- 503 bursts seen: one 2-in-a-row (survived), one 4-in-a-row (caused turn 7
  forfeit).
