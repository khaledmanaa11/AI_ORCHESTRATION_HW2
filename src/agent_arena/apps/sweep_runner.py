"""Sweep runner application for running ablation studies (Module J)."""
from __future__ import annotations

import argparse
import copy
import datetime
import hashlib
import json
import logging
import os
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

from agent_arena.apps.sweep_concurrency import execute_sweep_workers, streams_lock, summary_lock
from agent_arena.services.player.client import PlayerClient
from agent_arena.services.referee.brain.llm_brain import LLMRefereeBrain
from agent_arena.services.referee.brain.simple_brain import SimpleRefereeBrain
from agent_arena.services.referee.server import RefereeServer
from agent_arena.shared.api_gatekeeper import GatekeeperExhaustedError, get_default_gatekeeper
from agent_arena.shared.config import SetupConfig, load_setup_config

logger = logging.getLogger(__name__)


def hash_evidence_pack(path: str = "data/evidence_pack_primary.json") -> str:
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        h.update(f.read())
    return h.hexdigest()


def rewrite_summary(results_dir: Path, summary: dict) -> None:
    path = results_dir / "summary.json"
    fd, tmp_path = tempfile.mkstemp(dir=results_dir, prefix="summary_", suffix=".json")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)
    Path(tmp_path).replace(path)


def run_single_match(
    config: SetupConfig,
    judge_variant: str,
    seed: int,
    pro_master: bool,
    con_master: bool,
    ref_brain: Any,
    results_dir: Path,
    player_brain_choice: str = "seeded",
    move_timeout_seconds: float | None = None,
    ablated_vector: str | None = None,
) -> Any:
    """Run a single match and return final state, exceptions, and match_id."""
    cfg = copy.deepcopy(config)
    cfg.network.port = 0
    cfg.network.connect_timeout_seconds = 1.0
    cfg.network.read_timeout_seconds = 2.0 if player_brain_choice == "seeded" else 120.0
    cfg.game.move_timeout_seconds = move_timeout_seconds or (
        2.0 if player_brain_choice == "seeded" else max(cfg.game.move_timeout_seconds, 60.0)
    )
    cfg.debate.judge.variant = judge_variant
    cfg.debate.match.seed = seed
    cfg.debate.match.results_dir = str(results_dir)

    # Flip first_speaker for the second match in the mirror pair to net out position bias (E1)
    if not pro_master and con_master:
        current_first = cfg.debate.format.first_speaker
        cfg.debate.format.first_speaker = "CON" if current_first == "PRO" else "PRO"

    server = RefereeServer(cfg, brain=ref_brain)
    server.start()
    time.sleep(0.1)
    port = server.server.port

    exceptions: list[Exception] = []

    def launch_player(pid: str, p_seed: int, is_master: bool) -> None:
        try:
            p_cfg = copy.deepcopy(cfg)
            p_cfg.debate.player.brain_choice = player_brain_choice
            p_cfg.debate.player.ablation.master = is_master
            if is_master:
                p_cfg.debate.player.ablation.vectors = {
                    v: (v != ablated_vector) for v in p_cfg.debate.player.ablation.vectors
                }
            else:
                p_cfg.debate.player.ablation.vectors = {}
            client = PlayerClient(
                player_id=pid,
                host=cfg.network.host,
                port=port,
                connect_timeout=1.0,
                seed=p_seed,
                config=p_cfg,
            )
            client.start()
        except Exception as e:
            exceptions.append(e)

    t1 = threading.Thread(target=launch_player, args=("player_1", seed, pro_master), daemon=True)
    t2 = threading.Thread(target=launch_player, args=("player_2", seed, con_master), daemon=True)
    t1.start()
    t2.start()

    # Scale join deadline with the per-move timeout so LLM matches (60s+ per turn)
    # have room to finish before we tear sockets down. Seeded matches still wrap fast
    # because the threads exit on their own well before the deadline.
    match_deadline = max(120.0, cfg.game.move_timeout_seconds * 20.0)
    t1.join(timeout=match_deadline)
    t2.join(timeout=match_deadline)
    if server.game_thread:
        server.game_thread.join(timeout=match_deadline)

    server.stop()

    if server.exception:
        exceptions.append(server.exception)

    for e in exceptions:
        if isinstance(e, GatekeeperExhaustedError):
            raise e

    return server.final_state, server.exception, server.match_id


def write_streams(
    results_dir: Path,
    state: Any,
    seed: int,
    judge_variant: str,
    pro_master: bool,
    con_master: bool,
    match_id: str | None = None,
    run_id: str = "run_001",
    ablated_vector: str | None = None,
) -> None:
    """Process match results and append records to streams A, B, C."""
    if not state or not state.verdict:
        return
    m_id = match_id or "unknown"
    verdict = state.verdict
    winner = verdict.get("winner")
    margin = verdict.get("margin")
    rationale = verdict.get("rationale")
    motion = state.motion

    sa_path = results_dir / "stream_a_trajectory.jsonl"
    with sa_path.open("a", encoding="utf-8") as f:
        for tr in state.transcript:
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

    # Aggregate Stream B (player private-capture) (E2)
    sb_path = results_dir / "stream_b_private_capture.jsonl"
    run_dir = results_dir / run_id
    if run_dir.exists():
        for side in ("PRO", "CON"):
            p_file = run_dir / f"{m_id}.player_{side}.jsonl"
            if p_file.exists():
                try:
                    with p_file.open("r", encoding="utf-8") as pf:
                        rows = []
                        for line in pf:
                            line = line.strip()
                            if not line:
                                continue
                            row = json.loads(line)
                            row["match_id"] = m_id
                            row["seed"] = seed
                            if "turn_number" not in row:
                                row["turn_number"] = 0
                            rows.append(row)
                        if rows:
                            with sb_path.open("a", encoding="utf-8") as sbf:
                                for row in rows:
                                    sbf.write(json.dumps(row) + "\n")
                except Exception as e:
                    logger.error("Failed to aggregate private capture file %s: %s", p_file, e)

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
            "ablated_vector": ablated_vector,
        }) + "\n")


def run_sweep(
    config_path: str,
    k: int,
    sweep_id: str = "sweep_001",
    offline: bool = True,
    move_timeout_seconds: float | None = None,
    workers: int = 4,
    ablate: bool = False,
    variants: list[str] | None = None,
) -> None:
    """Run full sweep study over parameters (RJ2.1)."""
    config = load_setup_config(config_path)
    ref_brain = SimpleRefereeBrain() if offline else LLMRefereeBrain(provider=config.llm.provider)

    ablate = ablate or getattr(config.debate.match, "ablation_mode", False)

    max_conc = config.llm.gatekeeper.max_concurrency
    max_workers = max(1, min(workers, max_conc // 2))

    results_dir = Path(config.debate.match.results_dir) / sweep_id
    if results_dir.exists() and any(results_dir.iterdir()):
        raise SystemExit(
            f"Sweep directory {results_dir} is non-empty. "
            "Refusing to start. Pass a new --sweep-id or delete it."
        )

    results_dir.mkdir(parents=True, exist_ok=True)
    evidence_pack_sha256 = hash_evidence_pack("data/evidence_pack_primary.json")

    summary = {
        "evidence_pack_sha256": evidence_pack_sha256,
        "motion_id": config.debate.match.motion,
        "k": k,
        "started_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "total_matches": 0,
        "completed": 0,
        "forfeited": 0,
        "quota_aborted": 0,
        "pro_wins": 0,
        "con_wins": 0,
        "mean_margin": 0.0,
        "mean_turns": 0.0,
        "gatekeeper_final_snapshot": get_default_gatekeeper().snapshot(),
    }
    rewrite_summary(results_dir, summary)

    def update_summary(st: Any) -> None:
        with summary_lock:
            summary["total_matches"] += 1
            if st and st.verdict:
                reason = st.verdict.get("terminated_reason")
                if not reason:
                    summary["completed"] += 1
                elif reason == "disconnect":
                    summary["forfeited"] += 1
                elif reason == "aborted":
                    summary["quota_aborted"] += 1

                winner = st.verdict.get("winner")
                if winner == "PRO":
                    summary["pro_wins"] += 1
                elif winner == "CON":
                    summary["con_wins"] += 1

                margin = st.verdict.get("margin", 0)
                n = summary["total_matches"]
                summary["mean_margin"] = summary["mean_margin"] + (margin - summary["mean_margin"]) / n
                turns = len(st.transcript)
                summary["mean_turns"] = summary["mean_turns"] + (turns - summary["mean_turns"]) / n

            summary["gatekeeper_final_snapshot"] = get_default_gatekeeper().snapshot()
            rewrite_summary(results_dir, summary)

    def worker(variant: str, seed: int, pro_master: bool, con_master: bool, ablated_vector: str | None = None) -> None:
        player_brain_choice = "seeded" if offline else "llm"
        st, exc, match_id = run_single_match(
            config, variant, seed, pro_master, con_master, ref_brain,
            results_dir, player_brain_choice, move_timeout_seconds,
            ablated_vector=ablated_vector
        )
        if not exc:
            with streams_lock:
                write_streams(
                    results_dir, st, seed, variant, pro_master, con_master, match_id,
                    run_id=config.debate.match.run_id,
                    ablated_vector=ablated_vector
                )
        update_summary(st)

    work_items = []
    if ablate:
        variant = config.debate.judge.variant
        vectors = list(config.debate.player.ablation.vectors.keys())
        if not vectors:
            vectors = ["sycophancy", "authority", "bandwagon", "fallacy", "adaptive_persona", "bestN_judge_select", "read_targeting"]
        else:
            vectors = sorted(vectors)
        for seed in range(1, k + 1):
            for vector in vectors:
                work_items.append((variant, seed, True, False, vector))
                work_items.append((variant, seed, False, True, vector))
    else:
        active_variants = variants if variants else ["naive", "hardened", "structural"]
        for variant in active_variants:
            for seed in range(1, k + 1):
                work_items.append((variant, seed, True, False, None))
                work_items.append((variant, seed, False, True, None))

    execute_sweep_workers(
        work_items,
        worker,
        max_workers,
        summary,
        results_dir,
        rewrite_summary
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="config/setup.json")
    parser.add_argument("-k", type=int, default=None)
    parser.add_argument("--sweep-id", default="sweep_001", help="Sweep run identifier")
    parser.add_argument("--real", action="store_true", help="Use Gemini referee and player brains")
    parser.add_argument("--move-timeout", type=float, default=None)
    parser.add_argument("--workers", type=int, default=4, help="Number of workers")
    parser.add_argument("--ablate", action="store_true", help="Run per-vector one-at-a-time ablation sweep")
    parser.add_argument(
        "--variants", nargs="+", default=None,
        help="Judge variants to run (default: naive hardened structural). "
             "E.g. --variants debiased  or  --variants naive debiased",
    )
    args = parser.parse_args()

    k = args.k if args.k is not None else (42 if args.real else 10)
    run_sweep(
        args.config,
        k,
        sweep_id=args.sweep_id,
        offline=not args.real,
        move_timeout_seconds=args.move_timeout,
        workers=args.workers,
        ablate=args.ablate,
        variants=args.variants,
    )
