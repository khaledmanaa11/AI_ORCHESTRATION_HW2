"""Diagnostic factorial sweep to isolate causes of CON-leaning bias.

Varies three axes:
  1. Motion topic — original (AI autonomy), inverted (AI oversight), neutral (non-AI)
  2. Temperature — 0.0 (deterministic) vs 0.7 (sampled)
  3. Master ablation mirror — (PRO master, CON not) vs (PRO not, CON master)

Fixed: judge_variant="naive", k=2 seeds.

Total cells: 3 motions x 2 temps x 2 mirrors x 2 seeds = 24 matches.

Runs serially to keep LLM_TEMPERATURE env var clean across cells.
Expected wall time: ~60-75 min.
Writes results/diag_factorial/diag_results.jsonl (one record per cell).
"""
from __future__ import annotations

import copy
import json
import os
import time
from pathlib import Path

from agent_arena.apps.sweep_runner import run_single_match
from agent_arena.services.referee.brain.llm_brain import LLMRefereeBrain
from agent_arena.shared.config import load_setup_config

MOTIONS = {
    "AI_AUTONOMY": "Autonomous AI agents should be allowed to make consequential decisions without human approval",
    "AI_OVERSIGHT": "Human approval should be required before AI agents make any consequential decision",
    "NEUTRAL": "Universities should require all undergraduate students to study a foreign language for at least two years",
}

TEMPERATURES = [0.0, 0.7]
SEEDS = [1, 2]
MIRRORS = [(True, False), (False, True)]


def build_cells() -> list[dict]:
    cells = []
    for motion_key in MOTIONS:
        for temperature in TEMPERATURES:
            for seed in SEEDS:
                for pro_master, con_master in MIRRORS:
                    cells.append({
                        "motion_key": motion_key,
                        "temperature": temperature,
                        "seed": seed,
                        "pro_master": pro_master,
                        "con_master": con_master,
                    })
    return cells


def run_cell(cell: dict, base_cfg, out_dir: Path) -> dict:
    cfg = copy.deepcopy(base_cfg)
    cfg.debate.match.motion = MOTIONS[cell["motion_key"]]
    os.environ["LLM_TEMPERATURE"] = str(cell["temperature"])
    ref_brain = LLMRefereeBrain(provider=cfg.llm.provider)

    started = time.time()
    try:
        st, exc, mid = run_single_match(
            cfg, "naive", cell["seed"],
            cell["pro_master"], cell["con_master"],
            ref_brain, out_dir,
            player_brain_choice="llm",
            move_timeout_seconds=90,
        )
    except Exception as e:  # noqa: BLE001
        st, exc, mid = None, e, None
    elapsed = time.time() - started

    verdict = st.verdict if (st and st.verdict) else None
    terminated = verdict.get("terminated_reason") if verdict else None
    return {
        **cell,
        "match_id": mid,
        "completed": verdict is not None and not terminated,
        "terminated_reason": terminated,
        "winner": verdict.get("winner") if verdict else None,
        "margin": verdict.get("margin") if verdict else None,
        "rationale": (verdict.get("rationale") or "")[:400] if verdict else None,
        "error": str(exc) if exc else None,
        "elapsed_seconds": elapsed,
    }


def main() -> None:
    out_dir = Path("results/diag_factorial")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / "diag_results.jsonl"
    if out_path.exists():
        out_path.unlink()

    base_cfg = load_setup_config("config/setup.json")
    cells = build_cells()
    n = len(cells)
    print(f"=== Diagnostic factorial: {n} cells ===")
    print(f"Motions:      {list(MOTIONS.keys())}")
    print(f"Temperatures: {TEMPERATURES}")
    print(f"Seeds:        {SEEDS}")
    print(f"Mirrors:      {MIRRORS}")
    print(f"Output:       {out_path}")
    print()

    overall_start = time.time()
    for i, cell in enumerate(cells, 1):
        result = run_cell(cell, base_cfg, out_dir)
        with out_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(result) + "\n")

        total_min = (time.time() - overall_start) / 60.0
        eta_min = total_min * (n - i) / i if i > 0 else 0.0
        flag = "ok" if result["completed"] else f"FAIL({result.get('terminated_reason') or result.get('error', '?')[:30]})"
        print(
            f"[{i:>2}/{n}] {cell['motion_key']:<13} T={cell['temperature']} "
            f"seed={cell['seed']} pm={cell['pro_master']} cm={cell['con_master']} -> "
            f"winner={result['winner']} margin={result['margin']} "
            f"({result['elapsed_seconds']:.0f}s) [{flag}] "
            f"[+{total_min:.1f}m, ETA {eta_min:.1f}m]",
            flush=True,
        )

    print(f"\n=== Done in {(time.time() - overall_start) / 60.0:.1f} min ===")


if __name__ == "__main__":
    main()
