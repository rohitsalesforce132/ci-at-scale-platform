"""LogIndex — Searchable log index for fast retrieval."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set


@dataclass
class IndexedLog:
    """An indexed log entry."""
    job_id: str
    line_number: int
    severity: str
    message: str
    keywords: Set[str] = field(default_factory=set)


class LogIndex:
    """Searchable index over ingested CI logs.

    Maintains keyword, severity, and job-level indices for
    efficient retrieval without full scans.
    """

    def __init__(self) -> None:
        self._keyword_index: Dict[str, List[IndexedLog]] = {}
        self._severity_index: Dict[str, List[IndexedLog]] = {}
        self._job_index: Dict[str, List[IndexedLog]] = {}
        self._all_entries: List[IndexedLog] = []

    def index(self, job_id: str, logs: List[str]) -> int:
        """Index log lines for a job.

        Args:
            job_id: CI job identifier.
            logs: Raw log lines.

        Returns:
            Number of entries indexed.
        """
        count = 0
        for i, line in enumerate(logs):
            severity = self._classify(line)
            keywords = self._tokenize(line)
            entry = IndexedLog(
                job_id=job_id,
                line_number=i,
                severity=severity,
                message=line.strip(),
                keywords=keywords,
            )
            self._all_entries.append(entry)

            # job index
            if job_id not in self._job_index:
                self._job_index[job_id] = []
            self._job_index[job_id].append(entry)

            # severity index
            if severity not in self._severity_index:
                self._severity_index[severity] = []
            self._severity_index[severity].append(entry)

            # keyword index
            for kw in keywords:
                if kw not in self._keyword_index:
                    self._keyword_index[kw] = []
                self._keyword_index[kw].append(entry)

            count += 1
        return count

    def search(self, query: str, limit: int = 100) -> List[IndexedLog]:
        """Search indexed logs by query string.

        Args:
            query: Search query (keyword-based).
            limit: Maximum results to return.

        Returns:
            Matching indexed log entries.
        """
        terms = self._tokenize(query)
        if not terms:
            return self._all_entries[:limit]

        # Score entries by number of matching terms
        scores: Dict[int, int] = {}
        for term in terms:
            for entry in self._keyword_index.get(term, []):
                eid = id(entry)
                scores[eid] = scores.get(eid, 0) + 1

        # Sort by score descending
        scored = sorted(scores.items(), key=lambda x: -x[1])
        results = []
        seen: Set[int] = set()
        for eid, _ in scored:
            if eid in seen:
                continue
            seen.add(eid)
            for entry in self._all_entries:
                if id(entry) == eid:
                    results.append(entry)
                    break
            if len(results) >= limit:
                break
        return results

    def get_by_severity(self, severity: str) -> List[IndexedLog]:
        """Get all entries of a given severity.

        Args:
            severity: Severity level (ERROR, WARNING, INFO, etc.)

        Returns:
            Entries matching the severity.
        """
        return self._severity_index.get(severity.upper(), [])

    def compact(self) -> int:
        """Compact the index by deduplicating and pruning.

        Returns:
            Number of entries removed.
        """
        before = len(self._all_entries)
        # Deduplicate by (job_id, line_number)
        seen: Set[tuple] = set()
        unique: List[IndexedLog] = []
        for entry in self._all_entries:
            key = (entry.job_id, entry.line_number)
            if key not in seen:
                seen.add(key)
                unique.append(entry)
        self._all_entries = unique

        # Rebuild keyword index
        self._keyword_index.clear()
        for entry in self._all_entries:
            for kw in entry.keywords:
                if kw not in self._keyword_index:
                    self._keyword_index[kw] = []
                self._keyword_index[kw].append(entry)

        return before - len(self._all_entries)

    # -- helpers --

    def _classify(self, line: str) -> str:
        upper = line.upper()
        if any(kw in upper for kw in ("ERROR", "FAIL", "EXCEPTION")):
            return "ERROR"
        if any(kw in upper for kw in ("WARN",)):
            return "WARNING"
        return "INFO"

    def _tokenize(self, text: str) -> Set[str]:
        words: Set[str] = set()
        for w in text.lower().split():
            cleaned = "".join(c for c in w if c.isalnum())
            if len(cleaned) >= 3:
                words.add(cleaned)
        return words
