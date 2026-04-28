"""CommitAnalyzer — Analyze commit impact on CI."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class CommitInfo:
    """Information about a commit."""
    sha: str
    author: str
    message: str
    files_changed: List[str] = field(default_factory=list)
    additions: int = 0
    deletions: int = 0
    is_merge: bool = False


@dataclass
class ImpactAnalysis:
    """Result of commit impact analysis."""
    commit: CommitInfo
    risk_score: float
    affected_tests: List[str]
    estimated_ci_time: float
    requires_full_suite: bool


class CommitAnalyzer:
    """Analyze how commits impact CI workload.

    Estimates CI time, affected tests, and risk scores
    based on commit characteristics.
    """

    def __init__(self) -> None:
        self._test_file_map: Dict[str, List[str]] = {}  # file_pattern -> test_names
        self._commit_history: List[CommitInfo] = []

    def analyze(self, commit: CommitInfo) -> ImpactAnalysis:
        """Analyze the impact of a commit.

        Args:
            commit: Commit to analyze.

        Returns:
            ImpactAnalysis with risk and test info.
        """
        affected = self._find_affected_tests(commit)
        risk = self._compute_risk(commit, affected)
        ci_time = self._estimate_time(commit, len(affected))
        full_suite = risk > 0.7 or commit.is_merge

        self._commit_history.append(commit)

        return ImpactAnalysis(
            commit=commit,
            risk_score=risk,
            affected_tests=affected,
            estimated_ci_time=ci_time,
            requires_full_suite=full_suite,
        )

    def estimate_ci_time(self, commit: CommitInfo) -> float:
        """Estimate CI execution time for a commit.

        Args:
            commit: Commit to estimate.

        Returns:
            Estimated time in seconds.
        """
        affected = self._find_affected_tests(commit)
        return self._estimate_time(commit, len(affected))

    def get_affected_tests(self, commit: CommitInfo) -> List[str]:
        """Get tests affected by a commit.

        Args:
            commit: Commit to check.

        Returns:
            List of affected test names.
        """
        return self._find_affected_tests(commit)

    def compute_risk_score(self, commit: CommitInfo) -> float:
        """Compute risk score for a commit.

        Args:
            commit: Commit to score.

        Returns:
            Risk score (0.0 to 1.0).
        """
        affected = self._find_affected_tests(commit)
        return self._compute_risk(commit, affected)

    def add_test_mapping(self, file_pattern: str, tests: List[str]) -> None:
        """Register file-to-test mappings."""
        self._test_file_map[file_pattern] = tests

    # -- helpers --

    def _find_affected_tests(self, commit: CommitInfo) -> List[str]:
        tests: List[str] = []
        for f in commit.files_changed:
            for pattern, pattern_tests in self._test_file_map.items():
                if pattern in f or f.endswith(pattern):
                    tests.extend(pattern_tests)
        return list(set(tests))

    def _compute_risk(self, commit: CommitInfo, affected_tests: List[str]) -> float:
        score = 0.1  # baseline
        # More files = more risk
        score += min(0.3, len(commit.files_changed) * 0.05)
        # Large diffs = more risk
        score += min(0.2, (commit.additions + commit.deletions) / 1000 * 0.1)
        # More affected tests = more risk
        score += min(0.2, len(affected_tests) * 0.02)
        # Merge commits are higher risk
        if commit.is_merge:
            score += 0.15
        return min(1.0, score)

    def _estimate_time(self, commit: CommitInfo, test_count: int) -> float:
        base = 30.0  # base CI time
        per_test = 5.0  # seconds per test
        build_time = min(120, len(commit.files_changed) * 5)
        return base + build_time + test_count * per_test
