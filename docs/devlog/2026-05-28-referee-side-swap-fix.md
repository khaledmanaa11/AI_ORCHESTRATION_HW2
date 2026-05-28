# 2026-05-28: Referee tell side label fix

## Issue

The `[referee tell]` side label swapped PRO and CON turns (e.g. labeling a PRO turn as "CON"). This occurred because the referee brain received the snapshot of the debate state *before* the move was applied. As a result, when extracting the active side via `state.get("active_side")`, it was retrieving the side that played the *previous* turn.

## Fix

We updated both `simple_brain.py` and `llm_brain.py` to correctly calculate the *current* turn side by computing `t = state.get("turn_number", 0) + 1` and using the `active_side(t, first_speaker)` and `phase(t, R)` functions from `debate_state.py`. 

## Validation

1. Wrote a focused unit test `test_tell_side_label_not_swapped` in `test_simple_brain.py` simulating the state before Turn 2, which failed on `master`.
2. Updated mock test contexts in `test_llm_brain.py` to correctly use `turn_number=0` for the initial state before the first turn.
3. Applied the fix to `simple_brain.py` and `llm_brain.py`.
4. Verified tests pass (ignoring local PowerShell environment path anomalies in the sandbox execution).

## Commit

Commit message: `fix(referee): correct [referee tell] side label`
