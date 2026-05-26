"""Integration tests for the sweep runner (Module J)."""
from __future__ import annotations

import shutil
from pathlib import Path

from agent_arena.apps.sweep_runner import run_sweep


def test_sweep_runner_offline(tmp_path: Path) -> None:
    """Verify that run_sweep runs offline matches and outputs streams A and C."""
    # Build a temporary setup config
    config_src = Path("config/setup.json")
    assert config_src.exists()

    import json
    with config_src.open("r", encoding="utf-8") as f:
        data = json.load(f)

    # Point to the temporary path for results
    results_dir = tmp_path / "results"
    data["debate"]["match"]["results_dir"] = str(results_dir)
    data["debate"]["match"]["evidence_pack"] = "evidence_pack_primary"

    temp_config = tmp_path / "setup_test.json"
    with temp_config.open("w", encoding="utf-8") as f:
        json.dump(data, f)

    # Run sweep with k=1
    run_sweep(str(temp_config), k=1, offline=True)

    # Check that stream files exist and have content
    sa_file = results_dir / "stream_a_trajectory.jsonl"
    sc_file = results_dir / "stream_c_metadata.jsonl"

    assert sa_file.exists()
    assert sc_file.exists()

    with sa_file.open("r", encoding="utf-8") as f:
        sa_lines = f.readlines()
        assert len(sa_lines) > 0

    with sc_file.open("r", encoding="utf-8") as f:
        sc_lines = f.readlines()
        # 3 variants * 2 matches per variant = 6 metadata lines
        assert len(sc_lines) == 6

    shutil.rmtree(results_dir, ignore_errors=True)
