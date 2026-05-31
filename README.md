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

> **Note:** Full entry-point wiring is implemented in Phase 6 (Milestone M6).
> The commands below describe the intended workflow; stubs are in place now.

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
on both players. Real Gemini runs should use `--move-timeout 60` or higher so player
LLM calls have time to finish.

### Run a Sweep
```bash
uv run python -m agent_arena.apps.sweep_runner --config config/setup.json -k 1 --real
```

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

> Screenshots and annotated match logs will be added in `assets/` and `results/` once
> the integration milestone (M6) is complete.

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
| `llm.model_name` | string | `"gemini-2.5-flash-lite"` | Gemini model used by LLM brains in Phase 2 |

Logging is configured separately in `config/logging_config.json`.

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
1. Branch off `main`.
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
