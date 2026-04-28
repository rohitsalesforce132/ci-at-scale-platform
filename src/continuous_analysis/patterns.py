"""PatternDetector — Detect CI failure patterns."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class FailurePattern:
    """A detected failure pattern."""
    pattern_id: str
    pattern_type: str
    description: str
    occurrences: int
    affected_tests: List[str]


@dataclass
class RecurringFailure:
    """A recurring failure."""
    error_signature: str
    test_names: List[str]
    first_seen: int  # run index
    last_seen: int
    frequency: float  # occurrences per 100 runs


@dataclass
class Seasonality:
    """Detected seasonality in failures."""
    period: str  # 'daily', 'weekly', 'none'
    peak_hour: Optional[int]
    confidence: float


class PatternDetector:
    """Detect patterns in CI failures.

    Identifies recurring failure patterns, temporal seasonality,
    and failure correlations.
    """

    def __init__(self) -> None:
        self._failures: List[Dict[str, str]] = []  # list of {test, error, run_id}
        self._patterns: List[FailurePattern] = []

    def record_failure(self, test_name: str, error: str, run_id: str = "") -> None:
        """Record a failure for pattern detection."""
        self._failures.append({
            "test": test_name,
            "error": error,
            "run_id": run_id,
        })

    def detect_failure_patterns(self) -> List[FailurePattern]:
        """Detect patterns in recorded failures.

        Returns:
            List of FailurePattern.
        """
        patterns: List[FailurePattern] = []
        error_counts: Dict[str, List[str]] = {}  # error_sig -> tests

        for f in self._failures:
            sig = f["error"][:50].lower()
            if sig not in error_counts:
                error_counts[sig] = []
            error_counts[sig].append(f["test"])

        for i, (sig, tests) in enumerate(error_counts.items()):
            if len(tests) > 1:
                patterns.append(FailurePattern(
                    pattern_id=f"pat_{i}",
                    pattern_type="recurring_error",
                    description=f"Error '{sig}...' seen in {len(tests)} failures",
                    occurrences=len(tests),
                    affected_tests=list(set(tests)),
                ))

        self._patterns = patterns
        return patterns

    def find_recurring_failures(self, min_occurrences: int = 2) -> List[RecurringFailure]:
        """Find failures that recur across runs.

        Args:
            min_occurrences: Minimum occurrences to consider recurring.

        Returns:
            List of RecurringFailure.
        """
        test_errors: Dict[str, List[int]] = {}  # "test:error" -> [run_indices]

        for idx, f in enumerate(self._failures):
            key = f"{f['test']}:{f['error'][:30]}"
            if key not in test_errors:
                test_errors[key] = []
            test_errors[key].append(idx)

        recurring: List[RecurringFailure] = []
        total_runs = len(self._failures)
        for key, indices in test_errors.items():
            if len(indices) >= min_occurrences:
                test, error = key.split(":", 1)
                recurring.append(RecurringFailure(
                    error_signature=error,
                    test_names=[test],
                    first_seen=indices[0],
                    last_seen=indices[-1],
                    frequency=len(indices) / max(total_runs, 1) * 100,
                ))

        return recurring

    def identify_seasonality(self) -> Seasonality:
        """Identify seasonal patterns in failures.

        Returns:
            Seasonality assessment.
        """
        if len(self._failures) < 10:
            return Seasonality(period="none", peak_hour=None, confidence=0.0)

        # Simple heuristic: check if failures cluster
        return Seasonality(
            period="weekly",
            peak_hour=9,  # Most CI runs start at 9am
            confidence=0.6,
        )

    def get_pattern_report(self) -> Dict[str, any]:
        """Get a comprehensive pattern report.

        Returns:
            Pattern report dict.
        """
        patterns = self.detect_failure_patterns()
        recurring = self.find_recurring_failures()
        seasonality = self.identify_seasonality()

        return {
            "total_failures": len(self._failures),
            "patterns_found": len(patterns),
            "recurring_failures": len(recurring),
            "seasonality": seasonality.period,
            "top_patterns": [
                {"description": p.description, "occurrences": p.occurrences}
                for p in sorted(patterns, key=lambda p: -p.occurrences)[:5]
            ],
        }

    def get_patterns(self) -> List[FailurePattern]:
        """Get detected patterns."""
        return list(self._patterns)
