"""Unit tests for private-capture sink dump (Module P6, RP6.1-RP6.3)."""
from __future__ import annotations

import json
from pathlib import Path

from agent_arena.services.player.brain.capture import dump


def test_capture_dump_creates_dir_and_writes_records(tmp_path: Path) -> None:
    """Verify that dump creates directories and writes records correctly."""
    records = [
        {"turn_number": 1, "side": "PRO", "reflexion_lesson": "A"},
        {"turn_number": 2, "side": "PRO", "reflexion_lesson": "B"},
    ]
    results_dir = tmp_path / "results"
    run_id = "test_run_123"
    match_id = "test_match_456"
    side = "PRO"

    # Call dump (results_dir does not exist yet)
    dump(
        records=records,
        run_id=run_id,
        results_dir=str(results_dir),
        match_id=match_id,
        side=side,
        private_capture=True,
    )

    expected_path = results_dir / run_id / f"{match_id}.player_{side}.jsonl"
    assert expected_path.exists()

    # Read back records
    with expected_path.open("r", encoding="utf-8") as fh:
        lines = fh.readlines()

    assert len(lines) == 2
    assert json.loads(lines[0]) == records[0]
    assert json.loads(lines[1]) == records[1]


def test_capture_dump_gated_by_private_capture(tmp_path: Path) -> None:
    """Verify that no file/directory is created if private_capture is false."""
    records = [{"turn_number": 1, "side": "CON", "reflexion_lesson": "C"}]
    results_dir = tmp_path / "results"
    run_id = "test_run_123"
    match_id = "test_match_456"
    side = "CON"

    dump(
        records=records,
        run_id=run_id,
        results_dir=str(results_dir),
        match_id=match_id,
        side=side,
        private_capture=False,
    )

    expected_path = results_dir / run_id / f"{match_id}.player_{side}.jsonl"
    assert not expected_path.exists()
    assert not (results_dir / run_id).exists()


def test_capture_dump_exception_handling(tmp_path: Path) -> None:
    """Verify that exceptions during file write are logged and raised."""
    from unittest.mock import patch

    import pytest

    records = [{"turn_number": 1, "side": "CON"}]
    results_dir = tmp_path / "results"
    run_id = "test_run_123"
    match_id = "test_match_456"
    side = "CON"

    # Mock Path.open to raise an exception
    with patch.object(Path, "open", side_effect=OSError("Disk full")), pytest.raises(OSError, match="Disk full"):
        dump(
            records=records,
            run_id=run_id,
            results_dir=str(results_dir),
            match_id=match_id,
            side=side,
            private_capture=True,
        )


