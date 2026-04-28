"""RootCauseAnalyzer — Trace failures to root causes."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

from .diagnostician import Failure


@dataclass
class RootCause:
    """Identified root cause of a failure."""
    cause_type: str
    description: str
    commit_sha: Optional[str]
    evidence: List[str]
    confidence: float


@dataclass
class FailureHistory:
    """History of similar failures."""
    failure: Failure
    outcome: str  # 'fixed', 'recurring', 'new'


class RootCauseAnalyzer:
    """Analyze failures to trace them to root causes.

    Uses failure patterns, commit history, and evidence
    chains to identify the most likely root cause.
    """

    def __init__(self) -> None:
        self._commits: Dict[str, List[str]] = {}  # sha -> files
        self._failure_history: List[FailureHistory] = []

    def analyze(self, failure: Failure, history: Optional[List[FailureHistory]] = None) -> RootCause:
        """Analyze a failure with its history.

        Args:
            failure: The failure to analyze.
            history: Optional historical failures.

        Returns:
            RootCause with analysis results.
        """
        if history:
            self._failure_history.extend(history)

        cause_type = self._classify_cause(failure.error_message)
        commit_sha = self._find_related_commit(failure)
        evidence = self._gather_evidence(failure)
        confidence = self._compute_confidence(evidence)

        return RootCause(
            cause_type=cause_type,
            description=failure.error_message[:200],
            commit_sha=commit_sha,
            evidence=evidence,
            confidence=confidence,
        )

    def trace_to_commit(self, failure: Failure) -> Optional[str]:
        """Trace a failure to a specific commit.

        Args:
            failure: The failure.

        Returns:
            Commit SHA if found, else None.
        """
        cause = self.analyze(failure)
        return cause.commit_sha

    def classify_cause(self, failure: Failure) -> str:
        """Classify the cause type of a failure.

        Args:
            failure: The failure.

        Returns:
            Cause type string.
        """
        return self._classify_cause(failure.error_message)

    def get_evidence(self, cause: RootCause) -> List[str]:
        """Get evidence for a root cause.

        Args:
            cause: The root cause.

        Returns:
            List of evidence strings.
        """
        return cause.evidence

    def add_commit_info(self, sha: str, files: List[str]) -> None:
        """Register commit file changes."""
        self._commits[sha] = files

    # -- helpers --

    def _classify_cause(self, message: str) -> str:
        lower = message.lower()
        if "timeout" in lower:
            return "timeout"
        if "import" in lower or "module" in lower:
            return "dependency"
        if "assert" in lower:
            return "logic_change"
        if "connection" in lower or "network" in lower:
            return "infrastructure"
        if "memory" in lower or "oom" in lower:
            return "resource"
        return "code_change"

    def _find_related_commit(self, failure: Failure) -> Optional[str]:
        if failure.commit and failure.commit in self._commits:
            return failure.commit
        # Check recent commits for file overlaps
        return None

    def _gather_evidence(self, failure: Failure) -> List[str]:
        evidence = [f"Error message: {failure.error_message[:100]}"]
        if failure.test_name:
            evidence.append(f"Failing test: {failure.test_name}")
        if failure.commit:
            evidence.append(f"On commit: {failure.commit}")
            if failure.commit in self._commits:
                evidence.append(f"Changed files: {', '.join(self._commits[failure.commit][:3])}")
        return evidence

    def _compute_confidence(self, evidence: List[str]) -> float:
        base = 0.4
        if len(evidence) >= 2:
            base += 0.15
        if len(evidence) >= 3:
            base += 0.15
        if any("Changed files" in e for e in evidence):
            base += 0.2
        return min(0.95, base)
