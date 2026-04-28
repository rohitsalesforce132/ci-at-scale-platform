"""TestAnalytics — Comprehensive test analytics."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class TestHealth:
    """Health assessment of a test."""
    test_name: str
    pass_rate: float
    avg_duration: float
    flake_rate: float
    last_run_status: str
    health_score: float  # 0-100


@dataclass
class SuiteHealth:
    """Health assessment of a test suite."""
    suite_name: str
    total_tests: int
    passing_tests: int
    failing_tests: int
    flaky_tests: int
    avg_duration: float
    health_score: float


@dataclass
class TestRunRecord:
    """Record of a test run."""
    test_name: str
    passed: bool
    duration: float
    timestamp: float = 0.0
    commit: str = ""


class TestAnalytics:
    """Comprehensive test analytics and health tracking.

    Tracks pass rates, durations, flake rates, and trends
    across individual tests and entire suites.
    """

    def __init__(self) -> None:
        self._records: Dict[str, List[TestRunRecord]] = {}  # test_name -> runs
        self._suites: Dict[str, List[str]] = {}  # suite -> test_names

    def record_run(self, record: TestRunRecord) -> None:
        """Record a test run result."""
        if record.test_name not in self._records:
            self._records[record.test_name] = []
        self._records[record.test_name].append(record)

    def get_test_health(self, test_name: str) -> TestHealth:
        """Get health assessment for a test.

        Args:
            test_name: Test to assess.

        Returns:
            TestHealth with metrics.
        """
        runs = self._records.get(test_name, [])
        if not runs:
            return TestHealth(
                test_name=test_name, pass_rate=0.0, avg_duration=0.0,
                flake_rate=0.0, last_run_status="unknown", health_score=0.0,
            )

        passed = sum(1 for r in runs if r.passed)
        pass_rate = passed / len(runs)
        avg_dur = sum(r.duration for r in runs) / len(runs)
        last_status = "passed" if runs[-1].passed else "failed"

        # Flake rate = flip rate
        flips = sum(1 for i in range(1, len(runs)) if runs[i].passed != runs[i-1].passed)
        flake_rate = flips / max(len(runs) - 1, 1)

        health = pass_rate * 60 + (1 - flake_rate) * 20 + min(avg_dur, 30) / 30 * 20

        return TestHealth(
            test_name=test_name, pass_rate=pass_rate, avg_duration=avg_dur,
            flake_rate=flake_rate, last_run_status=last_status,
            health_score=min(100.0, health),
        )

    def get_suite_health(self, suite_name: str) -> SuiteHealth:
        """Get health assessment for a test suite.

        Args:
            suite_name: Suite to assess.

        Returns:
            SuiteHealth with aggregated metrics.
        """
        tests = self._suites.get(suite_name, [])
        if not tests:
            return SuiteHealth(suite_name=suite_name, total_tests=0,
                               passing_tests=0, failing_tests=0, flaky_tests=0,
                               avg_duration=0.0, health_score=0.0)

        total = len(tests)
        passing = 0
        failing = 0
        flaky = 0
        durations: List[float] = []

        for test in tests:
            health = self.get_test_health(test)
            durations.append(health.avg_duration)
            if health.last_run_status == "passed":
                passing += 1
            else:
                failing += 1
            if health.flake_rate > 0.2:
                flaky += 1

        avg_dur = sum(durations) / len(durations) if durations else 0.0
        health_score = (passing / total) * 100 if total else 0.0

        return SuiteHealth(
            suite_name=suite_name, total_tests=total,
            passing_tests=passing, failing_tests=failing, flaky_tests=flaky,
            avg_duration=avg_dur, health_score=health_score,
        )

    def compute_pass_rate(self, test_name: str, period: str = "7d") -> float:
        """Compute pass rate for a test.

        Args:
            test_name: Test name.
            period: Time period.

        Returns:
            Pass rate (0.0 to 1.0).
        """
        health = self.get_test_health(test_name)
        return health.pass_rate

    def get_trends(self, test_name: str) -> Dict[str, List[float]]:
        """Get trend data for a test.

        Args:
            test_name: Test name.

        Returns:
            Dict with duration and pass/fail trend lists.
        """
        runs = self._records.get(test_name, [])
        return {
            "durations": [r.duration for r in runs],
            "results": [1.0 if r.passed else 0.0 for r in runs],
        }

    def add_suite(self, suite_name: str, tests: List[str]) -> None:
        """Register a test suite."""
        self._suites[suite_name] = tests
