"""Integration tests for the sweep runner (Module J)."""
from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from agent_arena.apps.sweep_runner import run_sweep


def test_sweep_runner_offline_and_idempotency(tmp_path: Path) -> None:
    """Verify that run_sweep runs offline matches, outputs summary.json, streams A and C, and refuses overwrite."""
    config_src = Path("config/setup.json")
    assert config_src.exists()

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
    sc_file = sweep_dir / "stream_c_metadata.jsonl"
    summary_file = sweep_dir / "summary.json"

    assert sa_file.exists()
    assert sc_file.exists()
    assert summary_file.exists()

    with sa_file.open("r", encoding="utf-8") as f:
        sa_lines = f.readlines()
        assert len(sa_lines) > 0
        for line in sa_lines:
            json.loads(line)

    with sc_file.open("r", encoding="utf-8") as f:
        sc_lines = f.readlines()
        # 3 variants * 2 matches per variant * 2 for k=2 = 12 metadata lines
        assert len(sc_lines) == 12
        for line in sc_lines:
            json.loads(line)

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
