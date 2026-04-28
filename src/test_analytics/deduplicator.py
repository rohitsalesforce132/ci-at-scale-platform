"""TestDeduplicator — Find and consolidate redundant tests."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class TestProfile:
    """Profile of a test for deduplication analysis."""
    name: str
    covered_files: Set[str] = field(default_factory=set)
    covered_functions: Set[str] = field(default_factory=set)
    assertions: int = 0
    avg_duration: float = 0.0
    last_run_passed: bool = True


@dataclass
class DuplicationReport:
    """Report on test duplication."""
    test1: str
    test2: str
    overlap_score: float
    shared_files: Set[str]
    shared_functions: Set[str]


@dataclass
class ConsolidationSuggestion:
    """Suggestion for consolidating tests."""
    tests: List[str]
    reason: str
    estimated_savings: float  # in seconds


class TestDeduplicator:
    """Find and consolidate redundant tests.

    Analyzes test coverage overlap to identify tests that
    verify the same behavior and can be merged.
    """

    def __init__(self) -> None:
        self._profiles: Dict[str, TestProfile] = {}

    def add_profile(self, profile: TestProfile) -> None:
        """Register a test profile."""
        self._profiles[profile.name] = profile

    def find_duplicates(self, tests: Optional[List[str]] = None) -> List[DuplicationReport]:
        """Find duplicate or overlapping tests.

        Args:
            tests: Optional subset of tests to check.

        Returns:
            List of DuplicationReport for overlapping test pairs.
        """
        names = tests or list(self._profiles.keys())
        reports: List[DuplicationReport] = []

        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                p1 = self._profiles.get(names[i])
                p2 = self._profiles.get(names[j])
                if not p1 or not p2:
                    continue

                overlap = self.compute_overlap(p1, p2)
                if overlap.overlap_score >= 0.5:
                    reports.append(overlap)

        return sorted(reports, key=lambda r: -r.overlap_score)

    def compute_overlap(self, test1: TestProfile, test2: TestProfile) -> DuplicationReport:
        """Compute overlap between two tests.

        Args:
            test1: First test profile.
            test2: Second test profile.

        Returns:
            DuplicationReport with overlap analysis.
        """
        shared_files = test1.covered_files & test2.covered_files
        shared_funcs = test1.covered_functions & test2.covered_functions

        file_score = len(shared_files) / max(len(test1.covered_files | test2.covered_files), 1)
        func_score = len(shared_funcs) / max(len(test1.covered_functions | test2.covered_functions), 1)
        overlap_score = (file_score * 0.5 + func_score * 0.5)

        return DuplicationReport(
            test1=test1.name,
            test2=test2.name,
            overlap_score=overlap_score,
            shared_files=shared_files,
            shared_functions=shared_funcs,
        )

    def suggest_consolidations(self, tests: Optional[List[str]] = None) -> List[ConsolidationSuggestion]:
        """Suggest test consolidations.

        Args:
            tests: Optional test subset.

        Returns:
            Consolidation suggestions.
        """
        duplicates = self.find_duplicates(tests)
        suggestions: List[ConsolidationSuggestion] = []

        for dup in duplicates:
            p1 = self._profiles.get(dup.test1)
            p2 = self._profiles.get(dup.test2)
            if not p1 or not p2:
                continue

            savings = min(p1.avg_duration, p2.avg_duration)
            suggestions.append(ConsolidationSuggestion(
                tests=[dup.test1, dup.test2],
                reason=f"Overlap {dup.overlap_score:.0%} in {len(dup.shared_files)} files",
                estimated_savings=savings,
            ))

        return suggestions

    def estimate_savings(self, consolidations: List[ConsolidationSuggestion]) -> float:
        """Estimate total time savings from consolidations.

        Args:
            consolidations: Consolidation suggestions.

        Returns:
            Total estimated savings in seconds.
        """
        return sum(c.estimated_savings for c in consolidations)
