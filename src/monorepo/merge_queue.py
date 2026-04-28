"""MergeQueueManager — Manage merge queues for trunk-based development."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class PullRequest:
    """A pull request in the merge queue."""
    pr_id: str
    title: str
    author: str
    commit: str = ""
    priority: int = 5
    enqueued_at: float = 0.0
    ci_status: str = "pending"  # pending, passing, failing
    merge_ready: bool = False


@dataclass
class QueueStats:
    """Merge queue statistics."""
    total_prs: int
    pending_prs: int
    passing_prs: int
    failing_prs: int
    avg_wait_time: float


class MergeQueueManager:
    """Manage merge queues for trunk-based development.

    Maintains a priority queue of PRs waiting to merge,
    tracks CI status, and optimizes merge ordering.
    """

    def __init__(self) -> None:
        self._queue: List[PullRequest] = []
        self._merged: List[PullRequest] = []

    def enqueue(self, pr: PullRequest) -> int:
        """Add a PR to the merge queue.

        Args:
            pr: Pull request to enqueue.

        Returns:
            Position in queue (0-indexed).
        """
        pr.enqueued_at = time.time()
        self._queue.append(pr)
        self._queue.sort(key=lambda p: (p.priority, p.enqueued_at))
        return self._queue.index(pr)

    def dequeue(self, pr_id: str) -> Optional[PullRequest]:
        """Remove a PR from the queue.

        Args:
            pr_id: PR to dequeue.

        Returns:
            The dequeued PR, or None if not found.
        """
        for i, pr in enumerate(self._queue):
            if pr.pr_id == pr_id:
                removed = self._queue.pop(i)
                self._merged.append(removed)
                return removed
        return None

    def get_queue_position(self, pr_id: str) -> int:
        """Get the position of a PR in the queue.

        Args:
            pr_id: PR identifier.

        Returns:
            Position (0-indexed), or -1 if not in queue.
        """
        for i, pr in enumerate(self._queue):
            if pr.pr_id == pr_id:
                return i
        return -1

    def optimize_queue(self) -> List[str]:
        """Optimize the queue order.

        Reorders PRs to prioritize passing CI and high priority.

        Returns:
            Optimized PR ID list.
        """
        def sort_key(pr: PullRequest) -> tuple:
            ci_priority = 0 if pr.ci_status == "passing" else 1
            return (ci_priority, -pr.priority, pr.enqueued_at)

        self._queue.sort(key=sort_key)
        return [pr.pr_id for pr in self._queue]

    def get_queue_stats(self) -> QueueStats:
        """Get queue statistics.

        Returns:
            QueueStats with current metrics.
        """
        if not self._queue:
            return QueueStats(total_prs=0, pending_prs=0, passing_prs=0,
                              failing_prs=0, avg_wait_time=0.0)

        pending = sum(1 for p in self._queue if p.ci_status == "pending")
        passing = sum(1 for p in self._queue if p.ci_status == "passing")
        failing = sum(1 for p in self._queue if p.ci_status == "failing")

        now = time.time()
        wait_times = [now - p.enqueued_at for p in self._queue]
        avg_wait = sum(wait_times) / len(wait_times) if wait_times else 0.0

        return QueueStats(
            total_prs=len(self._queue),
            pending_prs=pending,
            passing_prs=passing,
            failing_prs=failing,
            avg_wait_time=avg_wait,
        )

    def update_ci_status(self, pr_id: str, status: str) -> bool:
        """Update CI status for a PR."""
        for pr in self._queue:
            if pr.pr_id == pr_id:
                pr.ci_status = status
                pr.merge_ready = status == "passing"
                return True
        return False

    def get_next_mergeable(self) -> Optional[PullRequest]:
        """Get the next PR ready to merge."""
        for pr in self._queue:
            if pr.merge_ready:
                return pr
        return None
