"""CoverageTracker — Track test coverage impact."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class CoverageRecord:
    """Coverage data for a commit."""
    commit: str
    line_coverage: float
    branch_coverage: float
    files_covered: Dict[str, float] = field(default_factory=dict)  # file -> coverage
    timestamp: float = 0.0


@dataclass
class CoverageGap:
    """A gap in test coverage."""
    file_path: str
    uncovered_lines: int
    risk_level: str  # 'high', 'medium', 'low'


class CoverageTracker:
    """Track test coverage trends and identify gaps.

    Monitors coverage changes per commit and flags areas
    where coverage is decreasing or insufficient.
    """

    def __init__(self) -> None:
        self._records: List[CoverageRecord] = []
        self._baseline: Optional[CoverageRecord] = None

    def track_coverage(self, record: CoverageRecord) -> None:
        """Track coverage for a commit.

        Args:
            record: Coverage data.
        """
        if not self._baseline:
            self._baseline = record
        self._records.append(record)

    def get_coverage_trend(self) -> List[Tuple[str, float]]:
        """Get coverage trend over time.

        Returns:
            List of (commit, line_coverage) tuples.
        """
        return [(r.commit, r.line_coverage) for r in self._records]

    def identify_gaps(self, threshold: float = 0.7) -> List[CoverageGap]:
        """Identify files with insufficient coverage.

        Args:
            threshold: Minimum coverage threshold.

        Returns:
            List of CoverageGap for under-covered files.
        """
        if not self._records:
            return []

        latest = self._records[-1]
        gaps: List[CoverageGap] = []
        for file_path, cov in latest.files_covered.items():
            if cov < threshold:
                risk = "high" if cov < 0.4 else ("medium" if cov < 0.6 else "low")
                gaps.append(CoverageGap(
                    file_path=file_path,
                    uncovered_lines=int((1 - cov) * 100),
                    risk_level=risk,
                ))
        return sorted(gaps, key=lambda g: g.uncovered_lines, reverse=True)

    def compute_risk(self, coverage_change: float) -> str:
        """Compute risk level for a coverage change.

        Args:
            coverage_change: Change in coverage (positive = improvement).

        Returns:
            Risk level string.
        """
        if coverage_change >= 0:
            return "low"
        if coverage_change > -0.02:
            return "low"
        if coverage_change > -0.05:
            return "medium"
        return "high"

    def get_latest(self) -> Optional[CoverageRecord]:
        """Get the most recent coverage record."""
        return self._records[-1] if self._records else None

    def get_change_from_baseline(self) -> float:
        """Get coverage change from baseline."""
        if not self._baseline or not self._records:
            return 0.0
        return self._records[-1].line_coverage - self._baseline.line_coverage
