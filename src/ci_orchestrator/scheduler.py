"""JobScheduler — Schedule and prioritize parallel CI jobs."""

from __future__ import annotations

import heapq
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Job:
    """A CI job to schedule."""
    job_id: str
    name: str
    priority: int = 5
    estimated_duration: float = 60.0
    requirements: Dict[str, int] = field(default_factory=dict)


@dataclass
class ScheduleResult:
    """Result of scheduling a job."""
    job_id: str
    worker: Optional[str]
    position: int
    estimated_start: float


class JobScheduler:
    """Schedule CI jobs with priority and resource awareness.

    Uses a priority queue to schedule jobs across available
    workers, optimizing for throughput and resource utilization.
    """

    def __init__(self, max_workers: int = 10) -> None:
        self._max_workers = max_workers
        self._queue: List[Tuple[int, float, str, Job]] = []  # (neg_priority, submit_time, id, job)
        self._running: Dict[str, Job] = {}
        self._completed: List[Job] = []
        self._counter = 0.0

    def schedule(self, job: Job, priority: Optional[int] = None) -> ScheduleResult:
        """Schedule a job for execution.

        Args:
            job: Job to schedule.
            priority: Override priority (lower = higher priority).

        Returns:
            ScheduleResult with placement info.
        """
        if priority is not None:
            job.priority = priority

        self._counter += 1
        heapq.heappush(self._queue, (-job.priority, self._counter, job.job_id, job))

        position = len(self._queue)
        # Try to assign to a worker if capacity available
        worker = None
        if len(self._running) < self._max_workers and position == 1:
            worker = self._assign_worker(job)

        return ScheduleResult(
            job_id=job.job_id,
            worker=worker,
            position=position,
            estimated_start=len(self._running) * job.estimated_duration / self._max_workers,
        )

    def get_queue_depth(self) -> int:
        """Get the number of jobs waiting in the queue.

        Returns:
            Queue depth.
        """
        return len(self._queue)

    def optimize_parallelism(self, jobs: List[Job]) -> Dict[str, int]:
        """Optimize parallel execution of jobs.

        Args:
            jobs: Jobs to optimize.

        Returns:
            Dict mapping job_id to suggested worker count.
        """
        result: Dict[str, int] = {}
        total_duration = sum(j.estimated_duration for j in jobs)
        if total_duration == 0:
            return {j.job_id: 1 for j in jobs}

        for job in jobs:
            # Allocate workers proportional to duration
            proportion = job.estimated_duration / total_duration
            workers = max(1, int(proportion * self._max_workers))
            result[job.job_id] = workers
        return result

    def get_utilization(self) -> float:
        """Get current worker utilization.

        Returns:
            Utilization percentage (0.0 to 1.0).
        """
        return len(self._running) / self._max_workers if self._max_workers > 0 else 0.0

    def _assign_worker(self, job: Job) -> str:
        worker_id = f"worker_{len(self._running)}"
        self._running[job.job_id] = job
        return worker_id

    def complete_job(self, job_id: str) -> bool:
        """Mark a job as completed."""
        if job_id in self._running:
            job = self._running.pop(job_id)
            self._completed.append(job)
            return True
        return False
