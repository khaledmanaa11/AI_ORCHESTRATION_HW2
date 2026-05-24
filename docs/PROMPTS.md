# Prompt-Engineering Log — Agent Arena

| Field | Value |
|-------|-------|
| Project | `agent-arena` |
| Version | 1.00 |
| Date started | 2026-05-24 |

> Follows guidelines §8.3. Every significant LLM interaction during development is recorded
> here: the context, the prompt, the output received, and lessons learned.
> This file is updated after every meaningful AI-assisted design or coding session.

---

## Entry 001 — Phase 0: Architecture & Document Authoring (2026-05-24)

### Context
Starting HW2 from scratch. Goal: design a three-process TCP multi-agent system (one referee
+ two players) that is game-agnostic and brain-agnostic, following Dr. Yoram Segal's
*Guidelines for Writing Professional Software* V3.00 strictly. No code yet — only PRD,
PLAN, and TODO documents for Phase 0.

### Prompt (paraphrased)
> "Build three files — PRD, PLAN, TODO — for a three-agent arena where one referee and two
> players run as separate OS processes communicating over TCP. No code. Follow the guidelines
> PDF strictly. Later the agents will use LLM brains."

### Key Design Decisions Made During This Session
1. **Three true OS processes** (not threads): referee = TCP server, players = TCP clients.
   Rationale: crash isolation; no redesign when moving from localhost to multi-host.
2. **Referee has a Brain** (not just players): the referee delegates game-level decisions
   (rule interpretation, scenario generation) to a `RefereeBrain` interface — placeholder
   in Phase 1, LLM-backed in Phase 2.
3. **No API Gatekeeper**: the project uses the author's Anthropic *user subscription* (not
   metered API billing) and is not deployed. A centralized rate-limiting gatekeeper would
   add complexity with no benefit. Decision documented in ADR-007; `PRD_gatekeeper.md`
   deleted.
4. **LLMCallerMixin** (shared/llm_caller.py): single Anthropic SDK wrapper inherited by
   both `referee/brain/llm_brain.py` and `player/brain/llm_brain.py`. Enforces DRY and
   satisfies guidelines §4.2 (OOP mixins).
5. **`match_id` is nullable on REGISTER**: the first message a player sends has no
   `match_id` yet (the match does not exist). The referee assigns the id in `REGISTER_ACK`.
   All subsequent messages carry it. Documented in ADR-008.
6. **`messages.py` split** into `envelope.py` + `payloads.py` to respect the ≤ 150-line
   file limit (AC7).
7. **`uv.lock` must be committed** (guidelines §8.4) — removed from `.gitignore`.

### Fixes Applied to Pre-existing Skeleton
| File | Problem | Fix |
|------|---------|-----|
| `.gitignore` | `uv.lock` listed (must be committed) | Removed; added `*.key`, `*.pem`, `credentials.json` |
| `pyproject.toml` | `line-length = 150` (should be 100 per §7.1) | Changed to 100; added `ignore = ["E501"]` |
| `pyproject.toml` | Missing `[tool.coverage.run/report]` | Added with `fail_under = 85`, `omit = apps/*` |
| `config/setup.json` | Missing `lobby_timeout`, `heartbeat_interval`, `llm.model_name` | Added all three |
| `shared/config.py` | Pydantic models missing new fields | Added `lobby_timeout_seconds`, `heartbeat_interval_seconds`, `LLMConfig` |
| `.env-example` | Had OPENAI_API_KEY and GEMINI_API_KEY (wrong providers) | Kept only ANTHROPIC_API_KEY |
| `README.md` | Mentioned "Centralized API gatekeeper" (removed design) | Rewritten; added all §2.1 mandatory sections |
| `docs/PRD_gatekeeper.md` | Entire file describes a removed design (ADR-007) | Deleted |

### Lessons Learned
- Defining the envelope schema early (especially `match_id` nullability) prevents protocol
  bugs that would require breaking changes later.
- The brain-interface abstraction (PlayerBrain / RefereeBrain) is the single most important
  seam in the system: it is what makes Phase 1 → Phase 2 a plug-swap, not a rewrite.
- Splitting `messages.py` at design time avoids a last-minute refactor when the file hits
  150 lines mid-implementation.

---

<!-- Add new entries below this line as development progresses. Format:
## Entry NNN — Phase X: <topic> (YYYY-MM-DD)
### Context
### Prompt (paraphrased)
### Output / Decision
### Lessons Learned
-->
