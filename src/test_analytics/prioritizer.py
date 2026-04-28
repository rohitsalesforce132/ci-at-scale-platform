"""TestPrioritizer — Prioritize test execution by impact."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class TestInfo:
    """Information about a test."""
    name: str
    avg_duration: float = 10.0
    failure_rate: float = 0.0
    last_failure_time: float = 0.0
    covered_files: List[str] = field(default_factory=list)
    priority: int = 5


@dataclass
class CommitFiles:
    """Files changed in a commit."""
    sha: str
    files: List[str] = field(default_factory=list)


class TestPrioritizer:
    """Prioritize test execution based on impact and risk.

    Orders tests to maximize early failure detection,
    considering code changes and test history.
    """

    def __init__(self) -> None:
        self._tests: Dict[str, TestInfo] = {}

    def prioritize(self, tests: List[str], commit: Optional[CommitFiles] = None) -> List[str]:
        """Prioritize tests for execution.

        Args:
            tests: Test names to prioritize.
            commit: Optional commit with changed files.

        Returns:
            Ordered list of test names (highest priority first).
        """
        scored: List[Tuple[float, str]] = []
        for test_name in tests:
            info = self._tests.get(test_name, TestInfo(name=test_name))
            score = self.compute_impact_score(info, commit)
            scored.append((-score, test_name))  # negative for descending sort
        scored.sort()
        return [name for _, name in scored]

    def compute_impact_score(self, test: TestInfo, commit: Optional[CommitFiles] = None) -> float:
        """Compute impact score for a test given a commit.

        Args:
            test: Test info.
            commit: Optional commit context.

        Returns:
            Impact score (higher = more important to run first).
        """
        score = 0.0
        # Higher failure rate = higher priority
        score += test.failure_rate * 40
        # Faster tests = run first (quick feedback)
        if test.avg_duration > 0:
            score += max(0, 20 - test.avg_duration)
        # Recent failures = higher priority
        if test.last_failure_time > 0:
            score += 15
        # Direct file overlap with commit
        if commit:
            overlap = len(set(test.covered_files) & set(commit.files))
            if overlap > 0:
                score += 30 * min(1.0, overlap / 3)
        return score

    def optimize_order(self, tests: List[TestInfo]) -> List[str]:
        """Optimize test execution order for fast feedback.

        Args:
            tests: Tests to order.

        Returns:
            Optimized test name list.
        """
        for t in tests:
            self._tests[t.name] = t
        return self.prioritize([t.name for t in tests])

    def get_critical_tests(self) -> List[str]:
        """Get tests marked as critical (high failure rate).

        Returns:
            List of critical test names.
        """
        critical = []
        for name, info in self._tests.items():
            if info.failure_rate > 0.3 or info.priority >= 8:
                critical.append(name)
        return critical

    def add_test(self, info: TestInfo) -> None:
        """Register a test."""
        self._tests[info.name] = info
