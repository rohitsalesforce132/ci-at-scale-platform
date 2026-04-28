"""RunTracker — Track CI runs and compute metrics."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class RunRecord:
    """Record of a CI run."""
    run_id: str
    metadata: Dict[str, Any] = field(default_factory=dict)
    start_time: float = 0.0
    end_time: float = 0.0
    status: str = "running"
    duration: float = 0.0


@dataclass
class Metrics:
    """Computed CI metrics for a period."""
    total_runs: int
    successful_runs: int
    failed_runs: int
    avg_duration: float
    p95_duration: float
    success_rate: float
    period: str


class RunTracker:
    """Track CI runs and compute performance metrics.

    Maintains run records and provides metrics computation
    over configurable time periods.
    """

    def __init__(self) -> None:
        self._runs: Dict[str, RunRecord] = {}

    def track_run(self, run_id: str, metadata: Optional[Dict[str, Any]] = None) -> RunRecord:
        """Track a new CI run.

        Args:
            run_id: Run identifier.
            metadata: Optional run metadata.

        Returns:
            Created RunRecord.
        """
        record = RunRecord(
            run_id=run_id,
            metadata=metadata or {},
            start_time=time.time(),
            status="running",
        )
        self._runs[run_id] = record
        return record

    def get_run(self, run_id: str) -> Optional[RunRecord]:
        """Get a run record.

        Args:
            run_id: Run identifier.

        Returns:
            RunRecord if found, else None.
        """
        return self._runs.get(run_id)

    def get_active_runs(self) -> List[RunRecord]:
        """Get all currently active (running) runs.

        Returns:
            List of active run records.
        """
        return [r for r in self._runs.values() if r.status == "running"]

    def compute_metrics(self, period: str = "1d") -> Metrics:
        """Compute CI metrics for a time period.

        Args:
            period: Time period (1d, 7d, 30d).

        Returns:
            Computed Metrics.
        """
        runs = list(self._runs.values())
        total = len(runs)
        if total == 0:
            return Metrics(
                total_runs=0,
                successful_runs=0,
                failed_runs=0,
                avg_duration=0.0,
                p95_duration=0.0,
                success_rate=0.0,
                period=period,
            )

        successful = sum(1 for r in runs if r.status == "success")
        failed = sum(1 for r in runs if r.status == "failed")
        durations = sorted(r.duration for r in runs if r.duration > 0)

        avg_dur = sum(durations) / len(durations) if durations else 0.0
        p95_idx = int(len(durations) * 0.95) if durations else 0
        p95_dur = durations[p95_idx] if durations and p95_idx < len(durations) else avg_dur

        return Metrics(
            total_runs=total,
            successful_runs=successful,
            failed_runs=failed,
            avg_duration=avg_dur,
            p95_duration=p95_dur,
            success_rate=successful / total,
            period=period,
        )

    def complete_run(self, run_id: str, status: str = "success") -> bool:
        """Mark a run as complete."""
        run = self._runs.get(run_id)
        if not run:
            return False
        run.end_time = time.time()
        run.duration = run.end_time - run.start_time
        run.status = status
        return True
