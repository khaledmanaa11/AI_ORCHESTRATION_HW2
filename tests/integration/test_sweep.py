"""Integration tests for the sweep runner (Module J)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from agent_arena.apps.sweep_runner import run_sweep


def test_sweep_runner_offline_and_idempotency(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that run_sweep runs offline matches, outputs summary.json, streams A, B, and C, and refuses overwrite."""
    config_src = Path("config/setup.json")
    assert config_src.exists()

    from agent_arena.services.player.brain.seeded_brain import SeededPlayerBrain
    original_generate = SeededPlayerBrain.generate

    def patched_generate(self, context):
        decision = original_generate(self, context)
        decision.trace = {
            "dummy_val": "test_trace_data",
            "turn_number": context.state.get("turn_number", 0) + 1
        }
        return decision

    monkeypatch.setattr(SeededPlayerBrain, "generate", patched_generate)

    with config_src.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # Point to the temporary path for results base dir
    results_base = tmp_path / "results"
    data["debate"]["match"]["results_dir"] = str(results_base)
    data["debate"]["match"]["evidence_pack"] = "evidence_pack_primary"

    temp_config = tmp_path / "setup_test.json"
    with temp_config.open("w", encoding="utf-8") as f:
        json.dump(data, f)

    sweep_id = "test_sweep_001"
    sweep_dir = results_base / sweep_id

    # Run sweep with k=2 and workers=2
    run_sweep(str(temp_config), k=2, sweep_id=sweep_id, offline=True, workers=2)

    # Check that the sweep dir was created
    assert sweep_dir.exists()

    # Check that stream files exist and have content
    sa_file = sweep_dir / "stream_a_trajectory.jsonl"
    sb_file = sweep_dir / "stream_b_private_capture.jsonl"
    sc_file = sweep_dir / "stream_c_metadata.jsonl"
    summary_file = sweep_dir / "summary.json"

    assert sa_file.exists()
    assert sb_file.exists()
    assert sc_file.exists()
    assert summary_file.exists()

    with sa_file.open("r", encoding="utf-8") as f:
        sa_lines = f.readlines()
        assert len(sa_lines) > 0
        for line in sa_lines:
            json.loads(line)

    with sb_file.open("r", encoding="utf-8") as f:
        sb_lines = f.readlines()
        assert len(sb_lines) > 0
        for line in sb_lines:
            row = json.loads(line)
            assert "match_id" in row
            assert "seed" in row
            assert "turn_number" in row
            assert row["dummy_val"] == "test_trace_data"

    # Assert that per-player capture files were not deleted (E2)
    run_dir = sweep_dir / "run_001"
    assert run_dir.exists()
    player_files = list(run_dir.glob("*.player_*.jsonl"))
    assert len(player_files) > 0

    with sc_file.open("r", encoding="utf-8") as f:
        sc_lines = f.readlines()
        # 3 variants * 2 matches per variant * 2 for k=2 = 12 metadata lines
        assert len(sc_lines) == 12
        pairs = {}
        for line in sc_lines:
            meta = json.loads(line)
            pair_id = meta["mirror_pair_id"]
            pairs.setdefault(pair_id, []).append(meta)

        assert len(pairs) == 6
        for pair_id, matches in pairs.items():
            assert len(matches) == 2, f"Expected 2 matches for {pair_id}, got {len(matches)}"
            fs1 = matches[0]["first_speaker"]
            fs2 = matches[1]["first_speaker"]
            assert {fs1, fs2} == {"PRO", "CON"}, f"Expected opposite first_speakers for {pair_id}, got {fs1} and {fs2}"

    with summary_file.open("r", encoding="utf-8") as f:
        summary = json.load(f)

    # Assert summary.json schema per FR-SW-5
    assert summary["total_matches"] == 12
    assert summary["completed"] == 12
    assert "forfeited" in summary
    assert "quota_aborted" in summary
    assert "pro_wins" in summary
    assert "con_wins" in summary
    assert "mean_margin" in summary
    assert "mean_turns" in summary
    assert "gatekeeper_final_snapshot" in summary
    assert "evidence_pack_sha256" in summary
    assert "motion_id" in summary
    assert "started_at" in summary

    # Run again, should exit with error message due to non-empty dir
    with pytest.raises(SystemExit) as exc:
        run_sweep(str(temp_config), k=2, sweep_id=sweep_id, offline=True, workers=2)

    assert "is non-empty" in str(exc.value)

    shutil.rmtree(results_base, ignore_errors=True)


def test_sweep_runner_ablation_mode(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that run_sweep in ablation mode runs matches, outputs summary.json, and records ablated_vector in Stream C."""
    config_src = Path("config/setup.json")
    assert config_src.exists()

    from agent_arena.services.player.brain.seeded_brain import SeededPlayerBrain
    original_generate = SeededPlayerBrain.generate

    def patched_generate(self, context):
        decision = original_generate(self, context)
        decision.trace = {
            "dummy_val": "test_trace_data",
            "turn_number": context.state.get("turn_number", 0) + 1
        }
        return decision

    monkeypatch.setattr(SeededPlayerBrain, "generate", patched_generate)

    with config_src.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # Force a specific judge variant and set vectors (so we have a clear set to ablate)
    data["debate"]["judge"]["variant"] = "naive"
    data["debate"]["player"]["ablation"]["vectors"] = {
        "sycophancy": False,
        "authority": False,
        "bandwagon": False,
        "fallacy": False,
        "adaptive_persona": False,
        "bestN_judge_select": False,
        "read_targeting": False
    }

    # Point to the temporary path for results base dir
    results_base = tmp_path / "results"
    data["debate"]["match"]["results_dir"] = str(results_base)
    data["debate"]["match"]["evidence_pack"] = "evidence_pack_primary"

    temp_config = tmp_path / "setup_test_ablation.json"
    with temp_config.open("w", encoding="utf-8") as f:
        json.dump(data, f)

    sweep_id = "test_sweep_ablation"
    sweep_dir = results_base / sweep_id

    # Run sweep in ablation mode with k=2 and workers=2
    run_sweep(str(temp_config), k=2, sweep_id=sweep_id, offline=True, workers=2, ablate=True)

    # Check that the sweep dir was created
    assert sweep_dir.exists()

    # Check that stream files exist and have content
    sa_file = sweep_dir / "stream_a_trajectory.jsonl"
    sb_file = sweep_dir / "stream_b_private_capture.jsonl"
    sc_file = sweep_dir / "stream_c_metadata.jsonl"
    summary_file = sweep_dir / "summary.json"

    assert sa_file.exists()
    assert sb_file.exists()
    assert sc_file.exists()
    assert summary_file.exists()

    # With k=2 and 7 vectors, total matches is 2 seeds * 7 vectors * 2 mirror matches = 28 matches
    with summary_file.open("r", encoding="utf-8") as f:
        summary = json.load(f)
    assert summary["total_matches"] == 28

    with sc_file.open("r", encoding="utf-8") as f:
        sc_lines = f.readlines()
        assert len(sc_lines) == 28
        for line in sc_lines:
            meta = json.loads(line)
            assert "ablated_vector" in meta
            assert meta["ablated_vector"] in {
                "sycophancy", "authority", "bandwagon", "fallacy", "adaptive_persona", "bestN_judge_select", "read_targeting"
            }
            # Verify judge variant is the one from config
            assert meta["judge_variant"] == "naive"

    shutil.rmtree(results_base, ignore_errors=True)

