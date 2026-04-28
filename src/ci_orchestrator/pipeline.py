"""PipelineOrchestrator — Manage CI pipelines."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class PipelineStatus(str, Enum):
    """Pipeline execution status."""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class PipelineConfig:
    """Pipeline configuration."""
    name: str
    steps: List[str] = field(default_factory=list)
    timeout: int = 3600
    parallel: bool = True


@dataclass
class PipelineRun:
    """A single pipeline execution."""
    run_id: str
    config: PipelineConfig
    status: PipelineStatus = PipelineStatus.PENDING
    commit: str = ""
    start_time: float = 0.0
    end_time: float = 0.0
    steps_completed: int = 0
    error: str = ""


class PipelineOrchestrator:
    """Manage CI pipeline lifecycle.

    Creates, triggers, monitors, and cancels pipelines.
    """

    def __init__(self) -> None:
        self._pipelines: Dict[str, PipelineConfig] = {}
        self._runs: Dict[str, PipelineRun] = {}
        self._run_counter = 0

    def create_pipeline(self, config: PipelineConfig) -> str:
        """Create a new pipeline configuration.

        Args:
            config: Pipeline configuration.

        Returns:
            Pipeline ID.
        """
        pid = f"pipe_{len(self._pipelines)}"
        self._pipelines[pid] = config
        return pid

    def trigger_pipeline(self, pipeline_id: str, commit: str = "") -> str:
        """Trigger a pipeline run.

        Args:
            pipeline_id: Pipeline to trigger.
            commit: Commit SHA.

        Returns:
            Run ID.
        """
        config = self._pipelines.get(pipeline_id)
        if not config:
            return ""

        self._run_counter += 1
        run_id = f"run_{self._run_counter}"
        run = PipelineRun(
            run_id=run_id,
            config=config,
            status=PipelineStatus.RUNNING,
            commit=commit,
            start_time=time.time(),
        )
        self._runs[run_id] = run
        return run_id

    def get_pipeline_status(self, run_id: str) -> Optional[PipelineStatus]:
        """Get the status of a pipeline run.

        Args:
            run_id: Run identifier.

        Returns:
            Pipeline status, or None if not found.
        """
        run = self._runs.get(run_id)
        return run.status if run else None

    def cancel_pipeline(self, run_id: str) -> bool:
        """Cancel a running pipeline.

        Args:
            run_id: Run to cancel.

        Returns:
            True if successfully cancelled.
        """
        run = self._runs.get(run_id)
        if not run or run.status != PipelineStatus.RUNNING:
            return False
        run.status = PipelineStatus.CANCELLED
        run.end_time = time.time()
        return True

    def complete_pipeline(self, run_id: str, success: bool = True, error: str = "") -> None:
        """Mark a pipeline run as complete."""
        run = self._runs.get(run_id)
        if run:
            run.status = PipelineStatus.SUCCESS if success else PipelineStatus.FAILED
            run.end_time = time.time()
            run.error = error

    def get_run(self, run_id: str) -> Optional[PipelineRun]:
        """Get a pipeline run."""
        return self._runs.get(run_id)

    def get_all_runs(self) -> List[PipelineRun]:
        """Get all pipeline runs."""
        return list(self._runs.values())
