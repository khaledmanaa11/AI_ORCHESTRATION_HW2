# PROGRESS — single source of truth

**NEXT: E5**

> Each session: do the step named in `NEXT`, then move `NEXT` to the line below it.
> Legend: `[ ]` todo · `[x]` done · `[!]` blocked (needs stronger model).
> Part files hold the detail. Do steps in this exact order.
> **Do not start Part H until every step in Parts B and C is `[x]`** (the canonical sweep
> needs a healthy gatekeeper and wired fault-tolerance, or it dies on an OPEN breaker).
> **Step H1 is `[HUMAN]`** — the user runs the live 252-match Gemini sweep personally. When an
> agent's `NEXT:` reaches H1, it must STOP and hand off. After the user finishes H1, the user
> sets H1 to `[x]` and `NEXT:` to `H2`, then agent sessions resume from H2.

---

## Part A — Runtime safety & small fixes → `PART_A_runtime_fixes.md`
- [x] A1 — Enforce `validate()` on inbound REGISTER + add `ErrorCode` enum + send typed error
- [x] A2 — Send `ERROR` before closing the 3rd+ connection
- [x] A3 — Replace hardcoded `"1.00"` with `PROTOCOL_VERSION` import in player agent
- [x] A4 — Narrow `TcpClient.connect` except clause (stop masking non-retryable errors)
- [x] A5 — Add `max_retries` + `backoff_base` to config; pass `max_frame_size` to FramedChannel
- [x] A6 — Delete duplicate `TERMINATED_*` constants in `result.py`, import from `constants`

## Part B — API Gatekeeper integration → `PART_B_gatekeeper.md`
- [x] B1 — Wire `APIGatekeeper` into referee_app; write `api_state` into verdict
- [x] B2 — Add `quota_aborted` handling branch in `_turn_runner`
- [x] B3 — Wire `APIGatekeeper` into player_app + agent; abort move on `GatekeeperError`
- [x] B4 — `print_transcript`: gatekeeper section + `quota_aborted` banner
- [x] B5 — Unit tests for `APIGatekeeper` (FakeClock, all behaviors)

## Part C — Fault-tolerance wiring → `PART_C_fault_tolerance.md`
- [x] C1 — Wire ShutdownCoordinator + WatchdogThread + HeartbeatSender into referee
- [x] C2 — Call `watchdog.heartbeat(player_id)` on every recv in `_turn_runner`
- [x] C3 — Wire fault-tolerance into player client/agent; GAME_OVER → request_shutdown
- [x] C4 — Fault-tolerance quality gate: ruff + coverage ≥85% on `shared/`, record in devlog

## Part D — Player generation params → `PART_D_player_params.md`
- [x] D1 — Thread temperature/top_p/seed from `gen_params` into the LLM call
- [x] D2 — Gate-guard test: no player brain module imports `google.generativeai`

## Part E — Referee sweep & analysis → `PART_E_referee_sweep.md`
- [x] E1 — `first_speaker` flip in sweep_runner mirror pairs
- [x] E2 — Stream B (player private-capture) aggregation in sweep_runner
- [x] E3 — Per-vector teardown (one-at-a-time ablation) mode in sweep_runner
- [x] E4 — Real citation grounding check in `LLMRefereeBrain._verify_grounding`
- [ ] E5 — Guard test: protocol dir unchanged + `PROTOCOL_VERSION == "1.00"`

## Part F — SDK & integration → `PART_F_sdk_integration.md`
- [ ] F1 — Implement `ArenaSDK.start_referee` / `start_player`
- [ ] F2 — Wire referee_app + player_app through `ArenaSDK`
- [ ] F3 — Move `LLMCallerMixin` to `shared/llm_caller.py`; both brains inherit it
- [ ] F4 — Real-TCP localhost integration test: referee + 2 players → GAME_OVER
- [ ] F5 — Enforce read/write socket timeouts after the handshake

## Part G — Docs & process reconciliation → `PART_G_docs.md`
- [ ] G1 — Reconcile Anthropic→Gemini in `PRD.md` + `PLAN.md`
- [ ] G2 — Write `docs/PRD_referee_brain.md`
- [ ] G3 — Write `PLAN_protocol.md` + `TODO_protocol.md`
- [ ] G4 — Write `PLAN_matchmaking.md` + `TODO_matchmaking.md`; fix PRD roles to PRO/CON
- [ ] G5 — Write `PLAN_game_engine.md` + `TODO_game_engine.md`; reconcile PRD signatures
- [ ] G6 — Fix stale statuses in `docs/TODO.md`

## Part H — Submission deliverables (LAST — needs B & C done) → `PART_H_submission.md`
- [ ] H1 — **[HUMAN]** Run canonical ≥250-match sweep into `results/sweep_001/` — _the user runs & supervises this; agents must STOP here, not run it_
- [ ] H2 — Rewrite `notebooks/analysis.ipynb` (parameterized, real values) + export `.html`
- [ ] H3 — Add ≥2 more entries to `docs/PROMPTS.md` (≥3 total)
- [ ] H4 — README: Troubleshooting + `llm.gatekeeper` config + Examples/screenshots
- [ ] H5 — Create `assets/architecture.png` (+ `.mmd` source)
- [ ] H6 — Final gate: pytest+ruff green, devlog, rewrite `CURRENT_STATE.md` snapshot

---

### Blocked steps (fill in as they happen)
- A1 (resolved 2026-05-30): the block was a **false alarm caused by the kit's verify commands**,
  not the code. The worker's A1 implementation was correct. Two kit bugs fixed: (1) `ruff check
  src tests` flags ~28 pre-existing unrelated errors; (2) a targeted `pytest <path>` trips the
  global 85% coverage gate. Both are now documented in `00_START_HERE.md` → "VERIFY — the real
  gate". A1 verified green (full suite 276 passed, 90.09% coverage) and committed.
