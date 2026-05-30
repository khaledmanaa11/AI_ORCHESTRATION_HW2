# PART E — Referee sweep & analysis

The experiment runner is missing pieces the PRD promises (bias-netting, Stream B, per-vector
ablation) and the LLM judge's grounding check is fake. Reference: `REMAINING_WORK.md` §5.

---

## E1 — `first_speaker` flip in mirror pairs
**Goal:** Each mirror pair of matches must swap which side speaks first, to net out
first-mover/position bias (PRD FR-EX2 / RJ2.2).
**Read first:**
- `src/agent_arena/apps/sweep_runner.py` (≈ 248–261 — the pair generation `(variant, seed, True, False)` / `(variant, seed, False, True)`, and the worker that runs a match)
- the config field controlling who speaks first (search for `first_speaker` in `config.py` / `setup.json` / matchmaking)
**Files (scope):** `apps/sweep_runner.py`.
**Do:** For the second match in each mirror pair, set the match config's `first_speaker` to the
opposite value before running. Make sure the flip is recorded in the match metadata (Stream C) so
analysis can see it.
**Verify:**
```
uv run ruff check src tests
uv run pytest tests/integration/test_sweep.py -q
```
Add/extend an assertion that the two matches in a pair have opposite `first_speaker`.
**Commit:** `fix(sweep): flip first_speaker in mirror pairs to net out position bias`

---

## E2 — Aggregate Stream B (player private-capture)
**Goal:** The sweep writes a `stream_b_private_capture.jsonl` joining each player's private
capture rows, alongside the existing Stream A (trajectory) and Stream C (metadata).
**Read first:**
- `src/agent_arena/apps/sweep_runner.py` (≈ 116, 138–165, 239–245 — `write_streams`, Stream A/C)
- `src/agent_arena/services/player/brain/capture.py` (≈ 12–39 — where per-player capture files are written under `results/`)
**Files (scope):** `apps/sweep_runner.py`.
**Do:** After each match, collect the per-player private-capture rows that `capture.py` produced
and append them to `stream_b_private_capture.jsonl`, keyed by `(match_id, seed, turn_number)` so
they join cleanly to Stream A. Do not delete the per-player files.
**Verify:**
```
uv run ruff check src tests
uv run pytest tests/integration/test_sweep.py -q
```
Assert a `stream_b_private_capture.jsonl` is produced and its rows carry the join keys.
**Commit:** `feat(sweep): aggregate player private-capture into stream B`

---

## E3 — Per-vector teardown (one-at-a-time ablation)
**Goal:** Add the ablation mode that disables exactly one evidence vector at a time, which PRD
FR-EX3 / RJ2.3 requires (TODO marks it done but it's absent).
**Read first:**
- `src/agent_arena/apps/sweep_runner.py` (the variant loop ≈ 248–261)
- `src/agent_arena/services/player/brain/player_prompts.py` (the per-vector gating already exists for prompts — reuse its vector names)
**Files (scope):** `apps/sweep_runner.py` (and a config flag in `config.py`/`setup.json` if needed to select the mode).
**Do:** Add a sweep mode that, for a baseline config, generates one run per evidence vector with
that single vector turned off (all others on), recording which vector was ablated in Stream C.
**Verify:**
```
uv run ruff check src tests
uv run pytest tests/integration/test_sweep.py -q
```
**Commit:** `feat(sweep): add per-vector one-at-a-time ablation mode`

---

## E4 — Real citation grounding in the LLM judge
**Goal:** `_verify_grounding` must check that a cited claim is actually supported by the evidence
pack content, not just that the pack's doc-id string appears literally in the utterance.
**Read first:**
- `src/agent_arena/services/referee/brain/llm_brain.py` (≈ 52–119, esp. `_verify_grounding` ≈ 96–102 — current naive `doc_id in text` check)
- the evidence pack shape: `data/evidence_pack_primary.json` (read, don't modify)
**Files (scope):** `services/referee/brain/llm_brain.py`.
**Do:** Replace the substring check with one that resolves each cited `doc_id` to its pack entry
and verifies the claim references that entry's actual content (e.g. the cited id exists in the
pack AND the quoted/paraphrased span maps to that entry). Keep it deterministic and offline.
**Verify:**
```
uv run ruff check src tests
uv run pytest tests/unit/services/referee/brain/test_llm_brain.py -q
```
Add a test: a citation to a non-existent / unsupported doc-id fails grounding; a real one passes.
**Commit:** `fix(referee): verify citations against evidence pack content, not substring`

---

## E5 — Guard: protocol frozen at v1.00
**Goal:** A test that fails if anyone changes the protocol package or bumps the version — the
homework requires the wire protocol stay frozen (RK.5 / AC9).
**Read first:**
- `src/agent_arena/constants.py` (line 5: `PROTOCOL_VERSION == "1.00"`)
- existing tests for a pattern to copy
**Files (scope):** new file `tests/unit/services/protocol/test_protocol_frozen.py` only.
**Do:** Write a test asserting `PROTOCOL_VERSION == "1.00"`. (Optionally also assert the set of
`MessageType` members matches a hardcoded expected set, so accidental additions fail the test.)
A git-diff-based CI check is nice-to-have but a value-based test is enough and runs anywhere.
**Verify:**
```
uv run ruff check src tests
uv run pytest tests/unit/services/protocol/test_protocol_frozen.py -q
```
**Commit:** `test(protocol): freeze PROTOCOL_VERSION and message-type set`
