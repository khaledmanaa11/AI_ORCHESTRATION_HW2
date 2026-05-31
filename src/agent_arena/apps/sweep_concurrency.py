"""Concurrency utilities for sweep runner."""
from __future__ import annotations

import concurrent.futures
import sys
import threading
from collections.abc import Callable
from typing import Any

from agent_arena.shared.api_gatekeeper import GatekeeperExhaustedError, get_default_gatekeeper

# Global locks for concurrent sweep runner
summary_lock = threading.Lock()
streams_lock = threading.Lock()

def execute_sweep_workers(
    work_items: list[tuple[str, int, bool, bool]],
    worker_fn: Callable[[str, int, bool, bool], None],
    max_workers: int,
    summary: dict[str, Any],
    results_dir: Any,
    rewrite_summary_fn: Callable[[Any, dict[str, Any]], None],
) -> None:
    """Run match workers concurrently, handling quota exhaustion."""
    futures = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        for item in work_items:
            futures.append(executor.submit(worker_fn, *item))

        try:
            for future in concurrent.futures.as_completed(futures):
                future.result()
        except GatekeeperExhaustedError:
            executor.shutdown(wait=True, cancel_futures=True)
            with summary_lock:
                summary["halted_reason"] = "quota_exhausted"
                summary["gatekeeper_final_snapshot"] = get_default_gatekeeper().snapshot()
                rewrite_summary_fn(results_dir, summary)
            sys.exit(2)
