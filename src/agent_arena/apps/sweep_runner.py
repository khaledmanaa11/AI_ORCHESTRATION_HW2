"""Sweep runner application for running ablation studies (Module J)."""
from __future__ import annotations

import argparse
import copy
import json
import logging
import threading
import time
from pathlib import Path
from typing import Any

from agent_arena.services.player.client import PlayerClient
from agent_arena.services.referee.brain.llm_brain import LLMRefereeBrain
from agent_arena.services.referee.brain.simple_brain import SimpleRefereeBrain
from agent_arena.services.referee.server import RefereeServer
from agent_arena.shared.config import SetupConfig, load_setup_config

logger = logging.getLogger(__name__)


def run_single_match(
    config: SetupConfig,
    judge_variant: str,
    seed: int,
    pro_master: bool,
    con_master: bool,
    ref_brain: Any,
) -> Any:
    """Run a single match and return final state, exceptions, and match_id."""
    cfg = copy.deepcopy(config)
    cfg.network.port = 0
    cfg.network.connect_timeout_seconds = 1.0
    cfg.network.read_timeout_seconds = 2.0
    cfg.game.move_timeout_seconds = 2.0
    cfg.debate.judge.variant = judge_variant
    cfg.debate.match.seed = seed
    cfg.debate.match.results_dir = "results"

    server = RefereeServer(cfg, brain=ref_brain)
    server.start()
    time.sleep(0.1)
    port = server.server.port

    def launch_player(pid: str, p_seed: int, is_master: bool) -> None:
        p_cfg = copy.deepcopy(cfg)
        p_cfg.debate.player.brain_choice = "seeded"  # Default/mocked setup
        p_cfg.debate.player.ablation.master = is_master
        p_cfg.debate.player.ablation.vectors = (
            dict.fromkeys(p_cfg.debate.player.ablation.vectors, True) if is_master else {}
        )
        client = PlayerClient(
            player_id=pid,
            host=cfg.network.host,
            port=port,
            connect_timeout=1.0,
            seed=p_seed,
            config=p_cfg,
        )
        client.start()

    t1 = threading.Thread(target=launch_player, args=("player_1", seed, pro_master), daemon=True)
    t2 = threading.Thread(target=launch_player, args=("player_2", seed, con_master), daemon=True)
    t1.start()
    t2.start()

    t1.join(timeout=10.0)
    t2.join(timeout=10.0)
    if server.game_thread:
        server.game_thread.join(timeout=10.0)

    server.stop()
    return server.final_state, server.exception


def write_streams(
    results_dir: Path,
    state: Any,
    seed: int,
    judge_variant: str,
    pro_master: bool,
    con_master: bool,
) -> None:
    """Process match results and append records to streams A, B, C."""
    if not state or not state.verdict:
        return
    m_id = state.rules_snapshot.get("match_id", "unknown")
    verdict = state.verdict
    winner = verdict.get("winner")
    margin = verdict.get("margin")
    rationale = verdict.get("rationale")
    motion = state.motion

    # Stream A: Verdict + Trajectory
    sa_path = results_dir / "stream_a_trajectory.jsonl"
    with sa_path.open("a", encoding="utf-8") as f:
        for tr in state.transcript:
            # Try to grab turn scores from referee score trajectory if available
            f.write(json.dumps({
                "match_id": m_id,
                "seed": seed,
                "turn_number": tr.turn_number,
                "side": tr.side,
                "phase": tr.phase,
                "winner": winner,
                "margin": margin,
                "final_verdict_rationale": rationale,
            }) + "\n")

    # Stream C: Metadata
    sc_path = results_dir / "stream_c_metadata.jsonl"
    with sc_path.open("a", encoding="utf-8") as f:
        f.write(json.dumps({
            "match_id": m_id,
            "seed": seed,
            "condition_cell": f"{judge_variant}_ON" if (pro_master or con_master) else f"{judge_variant}_OFF",
            "mirror_pair_id": f"pair_{judge_variant}_seed{seed}",
            "first_speaker": state.rules_snapshot.get("first_speaker", "PRO"),
            "terminated_reason": state.status if state.status != "COMPLETE" else None,
            "motion_id": motion,
            "evidence_pack_id": "evidence_pack_primary",
            "judge_variant": judge_variant,
            "player_ablation_master": pro_master or con_master,
        }) + "\n")


def run_sweep(config_path: str, k: int, offline: bool = True) -> None:
    """Run full sweep study over parameters (RJ2.1)."""
    config = load_setup_config(config_path)
    ref_brain = SimpleRefereeBrain() if offline else LLMRefereeBrain()
    results_dir = Path(config.debate.match.results_dir)
    results_dir.mkdir(parents=True, exist_ok=True)

    for variant in ["naive", "hardened", "structural"]:
        for seed in range(1, k + 1):
            # Match 1: PRO is ON, CON is OFF
            st1, exc1 = run_single_match(config, variant, seed, True, False, ref_brain)
            if not exc1:
                write_streams(results_dir, st1, seed, variant, True, False)

            # Match 2: PRO is OFF, CON is ON
            st2, exc2 = run_single_match(config, variant, seed, False, True, ref_brain)
            if not exc2:
                write_streams(results_dir, st2, seed, variant, False, True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/setup.json")
    parser.add_argument("-k", type=int, default=10)
    args = parser.parse_args()
    run_sweep(args.config, args.k, offline=True)
