"""Terminal-phase actions: trajectory dump for post-game analysis (S8, FR-FT7)."""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

TERMINATED_DISCONNECT = "disconnect"
TERMINATED_ABORTED = "aborted"


def write_trajectory(
    match_id: str,
    trajectory: list[dict[str, Any]],
    results_dir: Path | None,
) -> None:
    """Dump the per-turn private trajectory to results/{match_id}_trajectory.jsonl.

    Trajectory stays off-wire (2a/5.4e); dumped post-game only (6.d).
    Safe to call with results_dir=None (no-op) or on an empty trajectory.
    """
    if results_dir is None:
        return
    try:
        out = Path(results_dir) / f"{match_id}_trajectory.jsonl"
        out.parent.mkdir(parents=True, exist_ok=True)
        with out.open("w", encoding="utf-8") as fh:
            for row in trajectory:
                fh.write(json.dumps(row) + "\n")
        logger.debug("Wrote trajectory (%d rows) → %s", len(trajectory), out)
    except Exception:
        logger.exception("Failed to write trajectory for match=%s", match_id)
