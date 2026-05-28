# 2026-05-28 — Run 4: gatekeeper live validation (S1)

Triplet row: [TODO_submission.md §S1](../TODO_submission.md). This is the
post-gatekeeper acceptance run that gates S2–S8.

## Command

```powershell
uv run referee --config config/setup.json --brain llm --move-timeout 120 --show-transcript
```

Two `uv run player --brain llm` terminals (PlayerA, PlayerB) for the other
two seats. Branch `master`, commit `ebbd818` at run time. Capture:
[captures/run4-gatekeeper-live.log](captures/run4-gatekeeper-live.log).

## Result

- **Match ID:** `c4229c3e-0e26-44ca-a237-dd7babe3ba07`
- **Winner / margin:** CON, −0.46
- **Turns completed:** 10 / 10 (5 PRO, 5 CON, opening / rebuttal / closing
  structure correct)
- **Forfeits:** 0 PRO, 0 CON — no `0 words`, no `[referee flag] timeout`
- **No "partial debate" warning fired** — match ran clean to verdict

Per-turn word counts from the transcript: 137, 177, 128, 125, 156, 117,
125, 126, 132, 115. Every turn well above the forfeit-zero threshold.

Artifacts on disk:

```text
results/c4229c3e-0e26-44ca-a237-dd7babe3ba07_trajectory.jsonl   (10 lines, referee trace)
results/run_001/c4229c3e-...player_PRO.jsonl
results/run_001/c4229c3e-...player_CON.jsonl
```

## Httpx / 503 counts (referee terminal)

12 requests to `gemini-2.5-flash:generateContent` on the referee side:

- **503 clusters:** 1 cluster of length 1 (the very first request,
  immediately after both players connected). Auto-retried, next request
  came back 200.
- **429s:** 0.
- **All other 11 requests:** 200 OK.

Player-side httpx logs are in the player terminals (not bundled here);
neither player reported a forfeit or disconnect, so their retry budgets
were not exhausted. S1.2 numbers are recorded above.

## Verdict / gatekeeper inspection (S1.3)

The trajectory JSONL is per-turn `turn_scores` only — there is no
`flag` field on any row, which categorizes every turn as **success**
(no `timeout`, no `quota_aborted`). The verdict block is printed to
stdout only (captured in the log above) and likewise carries no
forfeit or quota flag.

Gatekeeper `api_state` snapshot: not emitted to disk in the current
build. The behavioral evidence is sufficient for S1.3 in this run —
no `GatekeeperOpenError`, no `GatekeeperExhaustedError`, no breaker
trip observed; the single 503 was absorbed by the in-client retry
without backing up into the gatekeeper. Wiring `api_state` into the
verdict JSON is a follow-up (not blocking submission).

## Judgement (S1.4)

**Pass.** The centralized API gatekeeper (commits `1dfc940`, `f89ad0c`)
shipped on top of the existing 429 backoff (`f1cc665`) survived its
first full live LLM-vs-LLM-vs-LLM match without forfeit, breaker trip,
or quota abort. Compared to Run 3 (commit `3a087b5`'s devlog), where a
4-burst 503 cluster cost turn 7 even with the forfeit-surfacing fix,
this run only saw a 1-cluster and absorbed it cleanly.

This is the gate. S2 (`[referee tell]` side-label fix), S3 (sweep),
S4 (notebook), S5 (PROMPTS log), S6 (README), S7 (diagram), S8 (final
gate) are unblocked.

## Side-notes (not blockers)

- The `[referee tell]` side-label bug is still visible — e.g. turn 04 is
  CON's rebuttal but the tell reads "The PRO side effectively refutes…",
  and turn 08 is CON's rebuttal but the tell reads "PRO delivers a strong
  rebuttal…". This is exactly the cosmetic mislabel already documented in
  `CURRENT_STATE.md` §Known Minor Bug and queued as S2. It does not feed
  the verdict path.
- Margin (−0.46) is meaningfully tighter than the first clean match
  (`a308b937`, −0.22) — different motion-seat assignment of bias not
  attempted here; one match is not a distribution. The sweep (S3) will
  give the distribution.
