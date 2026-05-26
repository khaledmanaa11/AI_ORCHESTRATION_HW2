"""Module P6 (Private-Capture Sink) implementation (FR-PC, BS-5)."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def dump(
    records: list[dict[str, Any]],
    run_id: str,
    results_dir: str,
    match_id: str,
    side: str,
    private_capture: bool = True,
) -> None:
    """Dump per-turn trace records to results/<run_id>/<match_id>.player_<side>.jsonl.

    One JSON object per line. Gated by private_capture.
    """
    if not private_capture:
        logger.debug("Private capture disabled, skipping dump for match %s (%s)", match_id, side)
        return

    out_dir = Path(results_dir) / run_id
    out_dir.mkdir(parents=True, exist_ok=True)

    out_file = out_dir / f"{match_id}.player_{side}.jsonl"
    try:
        with out_file.open("w", encoding="utf-8") as fh:
            for record in records:
                fh.write(json.dumps(record) + "\n")
        logger.debug("Wrote private capture (%d records) → %s", len(records), out_file)
    except Exception:
        logger.exception("Failed to write private capture for match=%s, side=%s", match_id, side)
        raise
