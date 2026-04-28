"""LogCorrelator — Correlate logs across CI jobs."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple


@dataclass
class CorrelationResult:
    """Result of correlating logs across jobs."""
    job_ids: List[str]
    common_errors: List[str]
    similarity_score: float
    shared_patterns: List[str]


@dataclass
class FailureGroup:
    """Group of related failures."""
    error_signature: str
    job_ids: List[str]
    count: int
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None


class LogCorrelator:
    """Correlate logs across multiple CI jobs.

    Identifies shared error patterns, groups similar failures,
    and tracks error propagation across the CI pipeline.
    """

    def __init__(self) -> None:
        self._error_signatures: Dict[str, List[Tuple[str, str]]] = {}  # sig -> [(job_id, error_line)]

    def correlate(self, job_logs: Dict[str, List[str]]) -> List[CorrelationResult]:
        """Correlate logs across multiple jobs.

        Args:
            job_logs: Dict mapping job_id to its log lines.

        Returns:
            Correlation results for related job pairs.
        """
        job_errors: Dict[str, Set[str]] = {}
        for job_id, logs in job_logs.items():
            errors: Set[str] = set()
            for line in logs:
                if self._is_error(line):
                    errors.add(self._normalize(line))
            job_errors[job_id] = errors

        results: List[CorrelationResult] = []
        job_ids = list(job_errors.keys())

        for i in range(len(job_ids)):
            for j in range(i + 1, len(job_ids)):
                j1, j2 = job_ids[i], job_ids[j]
                common = job_errors[j1] & job_errors[j2]
                if common:
                    union = job_errors[j1] | job_errors[j2]
                    score = len(common) / len(union) if union else 0.0
                    results.append(CorrelationResult(
                        job_ids=[j1, j2],
                        common_errors=list(common),
                        similarity_score=score,
                        shared_patterns=list(common)[:5],
                    ))
        return results

    def find_similar_errors(self, error_signature: str) -> List[Tuple[str, int]]:
        """Find jobs with similar error signatures.

        Args:
            error_signature: Normalized error text.

        Returns:
            List of (job_id, similarity_count) tuples.
        """
        normalized = self._normalize(error_signature)
        results: List[Tuple[str, int]] = []
        for sig, jobs in self._error_signatures.items():
            if self._fuzzy_match(normalized, sig):
                for job_id, _ in jobs:
                    results.append((job_id, len(jobs)))
        return results

    def group_failures(self, failures: Dict[str, List[str]]) -> List[FailureGroup]:
        """Group similar failures across jobs.

        Args:
            failures: Dict mapping job_id to list of failure messages.

        Returns:
            Grouped failures by error signature.
        """
        groups: Dict[str, FailureGroup] = {}
        for job_id, errors in failures.items():
            for error in errors:
                sig = self._normalize(error)
                # Check existing groups for similarity
                matched = False
                for existing_sig, group in groups.items():
                    if self._fuzzy_match(sig, existing_sig):
                        group.job_ids.append(job_id)
                        group.count += 1
                        group.last_seen = job_id
                        matched = True
                        break
                if not matched:
                    groups[sig] = FailureGroup(
                        error_signature=sig,
                        job_ids=[job_id],
                        count=1,
                        first_seen=job_id,
                        last_seen=job_id,
                    )
                # Track for future lookups
                if sig not in self._error_signatures:
                    self._error_signatures[sig] = []
                self._error_signatures[sig].append((job_id, error))

        return list(groups.values())

    # -- helpers --

    def _is_error(self, line: str) -> bool:
        upper = line.upper()
        return any(kw in upper for kw in ("ERROR", "FAIL", "EXCEPTION"))

    def _normalize(self, text: str) -> str:
        # Remove numbers, paths, and timestamps for signature matching
        import re
        result = text.lower().strip()
        result = re.sub(r'\d+', 'N', result)
        result = re.sub(r'/[\w/.-]+', 'PATH', result)
        return result[:200]

    def _fuzzy_match(self, sig1: str, sig2: str) -> bool:
        if sig1 == sig2:
            return True
        # Simple overlap check
        words1 = set(sig1.split())
        words2 = set(sig2.split())
        if not words1 or not words2:
            return False
        overlap = len(words1 & words2) / max(len(words1), len(words2))
        return overlap >= 0.6
