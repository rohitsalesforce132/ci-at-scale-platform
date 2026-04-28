"""FlakeDetector — Detect flaky tests from run history."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class TestRun:
    """A single test execution result."""
    test_name: str
    passed: bool
    run_id: str
    commit: str
    duration: float = 0.0


@dataclass
class FlakeReport:
    """Report on a potentially flaky test."""
    test_name: str
    flake_rate: float
    total_runs: int
    pass_count: int
    fail_count: int
    is_flaky: bool
    confidence: float


class FlakeDetector:
    """Detect flaky tests from historical run data.

    A test is considered flaky if it shows inconsistent pass/fail
    results across the same commit or across sequential runs.
    """

    def __init__(self) -> None:
        self._history: Dict[str, List[TestRun]] = {}

    def analyze_test_history(self, test_name: str, runs: Optional[List[TestRun]] = None) -> FlakeReport:
        """Analyze the pass/fail history of a test.

        Args:
            test_name: Name of the test.
            runs: Optional runs to analyze (uses stored history if None).

        Returns:
            FlakeReport with flake analysis.
        """
        if runs is not None:
            self._history[test_name] = runs

        test_runs = self._history.get(test_name, [])
        total = len(test_runs)
        if total == 0:
            return FlakeReport(
                test_name=test_name,
                flake_rate=0.0,
                total_runs=0,
                pass_count=0,
                fail_count=0,
                is_flaky=False,
                confidence=0.0,
            )

        pass_count = sum(1 for r in test_runs if r.passed)
        fail_count = total - pass_count
        flake_rate = fail_count / total if total > 0 else 0.0

        # Check for flip-flopping (key flake indicator)
        flips = 0
        for i in range(1, len(test_runs)):
            if test_runs[i].passed != test_runs[i - 1].passed:
                flips += 1
        flip_rate = flips / max(total - 1, 1)

        # Confidence based on sample size and flip rate
        confidence = min(1.0, total / 20.0) * min(1.0, flip_rate * 3)

        return FlakeReport(
            test_name=test_name,
            flake_rate=flake_rate,
            total_runs=total,
            pass_count=pass_count,
            fail_count=fail_count,
            is_flaky=flake_rate > 0.0 and flake_rate < 1.0 and flip_rate > 0.2,
            confidence=confidence,
        )

    def compute_flake_rate(self, test_name: str) -> float:
        """Compute the flake rate for a test.

        Args:
            test_name: Test name.

        Returns:
            Flake rate (0.0 to 1.0).
        """
        runs = self._history.get(test_name, [])
        if len(runs) < 2:
            return 0.0
        # Flake rate = proportion of runs that changed outcome from previous
        flips = 0
        for i in range(1, len(runs)):
            if runs[i].passed != runs[i - 1].passed:
                flips += 1
        return flips / (len(runs) - 1)

    def get_flaky_tests(self, threshold: float = 0.15) -> List[FlakeReport]:
        """Get all tests with flake rate above threshold.

        Args:
            threshold: Minimum flake rate to consider flaky.

        Returns:
            List of FlakeReport for flaky tests.
        """
        reports: List[FlakeReport] = []
        for test_name in self._history:
            report = self.analyze_test_history(test_name)
            if report.flake_rate >= threshold and report.is_flaky:
                reports.append(report)
        return reports

    def is_flake(self, test_name: str, failure: Optional[TestRun] = None) -> bool:
        """Check if a specific failure is likely a flake.

        Args:
            test_name: Test name.
            failure: The failure to check.

        Returns:
            True if likely a flake.
        """
        report = self.analyze_test_history(test_name)
        if not report.is_flaky:
            return False
        if failure:
            # If the test has passed more recently, it's more likely a flake
            runs = self._history.get(test_name, [])
            if len(runs) >= 2 and runs[-2].passed:
                return True
        return report.flake_rate < 0.5  # Not consistently failing
