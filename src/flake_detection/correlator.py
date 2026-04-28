"""FailureCorrelator — Correlate test failures with code changes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Commit:
    """A code commit."""
    sha: str
    author: str
    message: str
    files: List[str] = field(default_factory=list)
    timestamp: float = 0.0


@dataclass
class Failure:
    """A test failure."""
    test_name: str
    error_message: str
    commit: str
    job_id: str = ""


@dataclass
class CorrelationReport:
    """Report correlating failures with commits."""
    failure: Failure
    blamed_commit: Optional[Commit]
    confidence: float
    evidence: List[str]
    related_files: List[str]


class FailureCorrelator:
    """Correlate test failures with code changes.

    Uses file path matching and commit timing to identify
    which code changes likely caused test failures.
    """

    def __init__(self) -> None:
        self._commits: Dict[str, Commit] = {}
        self._test_file_map: Dict[str, List[str]] = {}  # test_name -> source files

    def correlate_failure(self, failure: Failure, commits: Optional[List[Commit]] = None) -> CorrelationReport:
        """Correlate a failure with code changes.

        Args:
            failure: The test failure.
            commits: Commits to check (uses stored if None).

        Returns:
            CorrelationReport with blame info.
        """
        if commits:
            for c in commits:
                self._commits[c.sha] = c

        related_files = self._test_file_map.get(failure.test_name, [])
        best_commit: Optional[Commit] = None
        best_confidence = 0.0
        evidence: List[str] = []

        for commit in self._commits.values():
            overlap = set(commit.files) & set(related_files) if related_files else set()
            if overlap:
                confidence = len(overlap) / max(len(related_files), 1)
                if confidence > best_confidence:
                    best_commit = commit
                    best_confidence = confidence
                    evidence = [f"File overlap: {f}" for f in overlap]
            # Check if commit message mentions test
            if failure.test_name.lower() in commit.message.lower():
                msg_confidence = 0.5
                if msg_confidence > best_confidence:
                    best_commit = commit
                    best_confidence = msg_confidence
                    evidence = [f"Test mentioned in commit message"]

        return CorrelationReport(
            failure=failure,
            blamed_commit=best_commit,
            confidence=best_confidence,
            evidence=evidence,
            related_files=related_files,
        )

    def find_root_cause(self, failure: Failure) -> Optional[Commit]:
        """Find the root cause commit for a failure.

        Args:
            failure: The test failure.

        Returns:
            Most likely root cause commit, or None.
        """
        report = self.correlate_failure(failure)
        return report.blamed_commit

    def blame_commit(self, failure: Failure) -> Optional[str]:
        """Get the SHA of the blamed commit.

        Args:
            failure: The test failure.

        Returns:
            SHA of blamed commit, or None.
        """
        report = self.correlate_failure(failure)
        return report.blamed_commit.sha if report.blamed_commit else None

    def get_correlation_report(self, failure: Failure) -> CorrelationReport:
        """Get full correlation report for a failure.

        Args:
            failure: The test failure.

        Returns:
            Detailed correlation report.
        """
        return self.correlate_failure(failure)

    def add_test_mapping(self, test_name: str, source_files: List[str]) -> None:
        """Register which source files a test covers."""
        self._test_file_map[test_name] = source_files
