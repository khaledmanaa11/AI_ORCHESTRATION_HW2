# Agent Arena

`agent-arena` is a network orchestration substrate for running **multi-agent, turn-based
matches** across three independent OS processes that communicate over TCP. A **Referee**
process manages game state and role assignment; two **Player** processes connect, receive
their roles, and play. Every agent has a swappable **Brain** — placeholder in Phase 1,
LLM-backed (Gemini) in Phase 2.

---

## Table of Contents
1. [Installation](#installation)
2. [Usage](#usage)
3. [Examples](#examples)
4. [Configuration Guide](#configuration-guide)
5. [Contribution Guidelines](#contribution-guidelines)
6. [License & Credits](#license--credits)

---

## Findings (TL;DR for graders)

- **Two sweeps shipped, 257 verdicts total** (`results/sweep_001/`, `results/sweep_full/`).
- **Headline finding**: the LLM judge has a **substantive CON-bias** that is *robust to every procedural intervention tested* (naive, hardened, structural, debiased, blind variants all produce pair-averaged margins in [-0.48, -0.22]). The mirror-pair design is what makes this finding falsifiable — see `notebooks/analysis.ipynb` §5 for the cell-output evidence, and `analysis/FINDINGS.md` for the full discussion plus 12 ranked follow-up fixes.
- **Architecture**: `assets/architecture.md` (Mermaid).
- **Submission snapshot**: `docs/CURRENT_STATE.md` "Submission Snapshot" section.

---

## Installation

### Prerequisites
- Python >= 3.10
- [`uv`](https://docs.astral.sh/uv/) — the **only** permitted package manager for this project

### Steps
```bash
# 1. Clone the repository
git clone https://github.com/khaledmanaa11/AI_ORCHESTRATION_HW2.git
cd AI_ORCHESTRATION_HW2

# 2. Install all dependencies (creates .venv automatically)
uv sync

# 3. (Phase 2 only) Set your Gemini API key
cp .env-example .env
# Edit .env and set GOOGLE_API_KEY=<your key>
```

---

## Usage

All three processes (referee + 2 players) are real and wired. Open three terminals
in the repo root.

### Start the Referee
```bash
uv run referee --config config/setup.json --brain llm --move-timeout 120 --show-transcript
```

### Start Player A
```bash
uv run player --config config/setup.json --name PlayerA --brain llm
```

### Start Player B (in a separate terminal)
```bash
uv run player --config config/setup.json --name PlayerB --brain llm
```

For a cheap local smoke test, use `--brain simple` on the referee and `--brain seeded`
on both players (no Gemini calls, deterministic). Real Gemini runs should use
`--move-timeout 60` or higher so player LLM calls have time to finish.

### Run a Sweep
The sweep runner is the entry point that produced the 257 verdicts in `results/`.

```bash
# Offline smoke (no API): 1 mirror pair × default variants, seeded brains
uv run python -m agent_arena.apps.sweep_runner --config config/setup.json -k 1

# Full real sweep: all 5 judge variants × K mirror pairs, real Gemini
uv run python -m agent_arena.apps.sweep_runner \
    --config config/setup.json -k 12 --real --all --include-baseline \
    --sweep-id sweep_full --workers 4
```

Key flags:

| Flag | Meaning |
|---|---|
| `-k N` | Number of mirror pairs per variant (each pair = 2 matches with sides flipped) |
| `--real` | Use Gemini referee + Gemini player brains (requires `GOOGLE_API_KEY`) |
| `--sweep-id NAME` | Output directory under `results/` (must be empty — guard prevents overwrite) |
| `--variants V1 V2` | Pick specific judge variants (default: `naive hardened structural debiased`) |
| `--all` | Add `blind` judge variant on top of defaults |
| `--include-baseline` | Add the `motion_neutral` control condition |
| `--ablate` | Per-vector one-at-a-time ablation sweep |
| `--workers N` | Concurrent matches (default 4; respects `llm.gatekeeper.max_concurrency`) |
| `--move-timeout SEC` | Per-move LLM timeout |

Each sweep writes `results/<sweep-id>/<match-uuid>_trajectory.jsonl` per match plus
`summary.json` (aggregate verdicts, gatekeeper final snapshot) and
`stream_c_metadata.jsonl` (per-match metadata used by the analysis notebook).

### Run Tests
```bash
uv run pytest
```

### Lint
```bash
uv run ruff check
```
Scope is `src/` + `tests/` only — `notebooks/`, `scripts/`, and `analysis/` are excluded
in `pyproject.toml` because the exploratory style there (one-liners, inline `open()`) is
intentional.

---

## Examples

### Reproduce the headline finding (5 minutes, no code edits)

1. Open `notebooks/analysis.html` in any browser — fully baked, no kernel needed.
   Section 5 is the mirror-pair-corrected CON-bias result; the bar chart shows
   all five judge variants landing in the **[-0.48, -0.22]** margin band.
2. Read `analysis/FINDINGS.md` for the 12 ranked observations + 12 ranked fixes
   (A–L). The "Headline" block at the top is the falsifiable claim.
3. Re-run the analysis from raw data:
   ```bash
   uv run jupyter nbconvert --to notebook --execute notebooks/analysis.ipynb \
       --output analysis_repro.ipynb
   ```

### Inspect a real match

A single match trajectory is one JSONL file under `results/`. Each line is one
turn-record from the referee's perspective. Sample:

```bash
# A baked match from the full sweep (PRO motion, real Gemini, 10 turns)
cat results/sweep_full/00d739a3-baad-4fc2-b7b7-0568565dcb28_trajectory.jsonl | head -1
```

The corresponding **verdict** is in `summary.json`:

```bash
cat results/sweep_full/summary.json
```

```jsonc
{
  "evidence_pack_sha256": "bade1451...",
  "motion_id": "Autonomous AI agents should be allowed to make consequential decisions...",
  "k": 10,
  "total_matches": 120, "completed": 96, "forfeited": 24, "quota_aborted": 0,
  "pro_wins": 34, "con_wins": 86, "mean_margin": -0.469, "mean_turns": 8.0,
  "gatekeeper_final_snapshot": { "breaker_state": "CLOSED", "in_flight": 0, ... }
}
```

### Architecture

See [`assets/architecture.md`](assets/architecture.md) for the rendered Mermaid
diagram (3 processes, TCP transport, brain seams).

---

## Configuration Guide

All operational values live in `config/setup.json`. No hardcoded values appear in source.

| Key path | Type | Default | Description |
|----------|------|---------|-------------|
| `version` | string | `"1.00"` | Config schema version — must match `constants.EXPECTED_CONFIG_VERSION` |
| `network.host` | string | `"127.0.0.1"` | IP address the referee binds to |
| `network.port` | int | `9000` | TCP port the referee listens on |
| `network.player_count` | int | `2` | Exact number of players required before a match starts |
| `network.connect_timeout_seconds` | float | `5.0` | Timeout for a player's TCP connect attempt |
| `network.read_timeout_seconds` | float | `15.0` | Socket read timeout per message |
| `game.move_timeout_seconds` | float | `10.0` | Maximum time a player may take per move; violation policy set in source constants |
| `game.lobby_timeout_seconds` | float | `30.0` | Maximum wait for all players to register; expired lobby closes gracefully |
| `game.heartbeat_interval_seconds` | float | `5.0` | Interval between keep-alive heartbeat messages |
| `framing.max_frame_size_bytes` | int | `10485760` | Maximum TCP frame payload size (10 MiB) |
| `llm.provider` | string | `"google"` | LLM provider seam: `"google"` (direct `google.genai` SDK) or `"gemini-cli"` (local shim) |
| `llm.model_name` | string | `"gemini-2.5-flash"` | Gemini model used by LLM brains |
| `llm.generation_seed` | int | `42` | Seed forwarded into player/referee generation params |
| `llm.gatekeeper.rpm` | int | `2000` | Token-bucket refill rate (requests per minute) |
| `llm.gatekeeper.rpd` | int | `10000` | Daily request cap; triggers `GatekeeperExhaustedError` |
| `llm.gatekeeper.max_concurrency` | int | `8` | In-flight call cap across all threads |
| `llm.gatekeeper.breaker_threshold` | int | `15` | Failures within `breaker_window_seconds` to OPEN the breaker |
| `llm.gatekeeper.breaker_window_seconds` | float | `60.0` | Rolling window for failure counting |
| `llm.gatekeeper.breaker_cooldown_seconds` | float | `180.0` | OPEN → HALF_OPEN delay before probe |
| `llm.gatekeeper.acquire_timeout_seconds` | float | `180.0` | Per-acquire wait before `GatekeeperTimeoutError` |
| `debate.format.rebuttal_rounds` | int | `3` | Rebuttal rounds (drives turn count: opening + N rebuttals + closing per side) |
| `debate.format.word_cap` | int | `250` | Per-turn word cap (enforced by referee) |
| `debate.format.first_speaker` | string | `"PRO"` | Which side opens; flipped per mirror pair in sweeps |
| `debate.judge.variant` | string | `"naive"` | One of `naive` / `hardened` / `structural` / `debiased` / `blind` / `motion_neutral` |
| `debate.judge.weights` | object | `{logic:30, evidence:30, rebuttal:25, persuasion:15}` | Rubric weights summing to 100 |
| `debate.player.brain_choice` | string | `"seeded"` | `"seeded"` (deterministic) or `"llm"` (Gemini) |
| `debate.player.best_of_N` | int | `1` | Candidate utterances per turn; selector picks the best |
| `debate.player.temperature` | float | `0.7` | LLM sampling temperature |
| `debate.player.top_p` | float | `0.9` | LLM nucleus-sampling cutoff |
| `debate.player.selector_weights` | object | (all `1.0`) | Per-vector weights (`sycophancy`, `authority`, `bandwagon`, `fallacy`) for `best_of_N` selection |
| `debate.player.private_capture` | bool | `true` | Write per-player private trajectories under `results/run_id/` |
| `debate.player.ablation.master` | bool | `false` | Master switch for vector ablations |
| `debate.player.ablation.vectors` | object | (all `false`) | Per-vector on/off when `master=true` |
| `debate.player.ablation.baseline_mode` | string | `"beta"` | `"alpha"` / `"beta"` baseline prompt mode |
| `debate.match.motion` | string | (HFT ban) | Motion text used by single-match runs |
| `debate.match.evidence_pack` | string | `"evidence_pack_primary"` | Pack name (resolved under `data/`) |
| `debate.match.seed` | int | `42` | Match seed (role assignment, sampling) |
| `debate.match.run_id` | string | `"run_001"` | Subdir under `results_dir` for private captures |
| `debate.match.results_dir` | string | `"results"` | Top-level results directory |

Logging is configured separately in `config/logging_config.json`.

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `GatekeeperOpenError` | Breaker tripped: `breaker_threshold` failures inside `breaker_window_seconds`. Sweep clean-halts. | Wait `breaker_cooldown_seconds`; check `summary.json → gatekeeper_final_snapshot` to see why. Often a transient Gemini 503 storm — retry the sweep. |
| `GatekeeperExhaustedError` | Hit `llm.gatekeeper.rpd` (daily cap). | Wait until UTC midnight (or raise `rpd` in `config/setup.json` if your paid quota allows). |
| `GatekeeperTimeoutError` | Waited `acquire_timeout_seconds` for a token slot. | Lower `--workers` or raise `max_concurrency`. |
| Gemini `503 UNAVAILABLE` mid-match | Upstream model overload. Client auto-retries with backoff (`llm_client.py`). | No action needed if it recovers; if persistent, lower `--workers`. |
| Gemini `429 RESOURCE_EXHAUSTED` | Per-minute quota. Backoff honors `Retry-After`. | No action; if persistent, lower `rpm` or `--workers`. |
| `OSError: [WinError 10048]` / port in use | A previous referee didn't release `network.port`. | `netstat -ano \| findstr 9000`, kill the PID, or change `network.port`. |
| Sweep refuses to start, "directory not empty" | Idempotency guard on `--sweep-id`. | Use a fresh `--sweep-id` or `rm -rf results/<sweep-id>/`. |
| Match forfeits with `terminated_reason=disconnect` | Player crashed or `move_timeout_seconds` exceeded. | Raise `--move-timeout`; check the player terminal's stderr. |
| `GOOGLE_API_KEY` not set on `--real` runs | `.env` missing or `python-dotenv` didn't load. | `cp .env-example .env`, fill in the key, retry. Never commit `.env`. |

---

## Contribution Guidelines

### Code Style
- **Formatter / linter:** `ruff` — run `uv run ruff check` and `uv run ruff format` before every commit.
- **Line length:** 100 characters.
- **Files:** ≤ 150 code lines each; split modules when approaching the limit.
- **No magic strings:** all constants in `src/agent_arena/constants.py`.
- **No hardcoded config:** host, port, timeouts, model names all come from `config/setup.json`.
- **Secrets:** never in source; use `.env` (git-ignored); document in `.env-example`.

### Testing
- TDD: write tests alongside or before each module.
- Global coverage target: ≥ 85 % (`uv run pytest` enforces this).
- Transport must be mocked in unit tests (no live sockets required).

### Pull Request Process
1. Branch off `master`.
2. Apply all changes; ensure `uv run ruff check` reports 0 violations and `uv run pytest` passes.
3. Open a PR with a description that maps changes to task IDs from `docs/TODO.md`.
4. Request review; merge only after approval.

---

## License & Credits

**Author:** Khaled
**Course:** AI Orchestration — HW2
**Institution:** Semester 6

This project is developed as a course assignment and is not licensed for public redistribution.
Companion documents: [`docs/PRD.md`](docs/PRD.md) · [`docs/PLAN.md`](docs/PLAN.md) · [`docs/TODO.md`](docs/TODO.md)
