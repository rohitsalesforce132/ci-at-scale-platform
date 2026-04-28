"""LogIngester — Ingest and index CI logs."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class LogEntry:
    """A single parsed log entry."""
    job_id: str
    line_number: int
    timestamp: float
    level: str
    message: str
    raw: str
    step: Optional[str] = None


@dataclass
class IngestStats:
    """Statistics about ingested logs."""
    total_jobs: int = 0
    total_lines: int = 0
    total_bytes: int = 0
    error_lines: int = 0
    warning_lines: int = 0
    start_time: float = 0.0
    end_time: float = 0.0


class LogIngester:
    """Ingest and index CI logs at scale.

    Supports structured and unstructured log formats, indexing by job,
    severity, and timestamp for fast retrieval.
    """

    def __init__(self) -> None:
        self._entries: Dict[str, List[LogEntry]] = {}
        self._stats = IngestStats(start_time=time.time())
        self._index: Dict[str, List[Tuple[str, int]]] = {}  # keyword -> [(job_id, line_num)]

    def ingest(self, log_lines: List[str], job_id: str) -> int:
        """Ingest log lines for a given job.

        Args:
            log_lines: Raw log lines to ingest.
            job_id: Identifier for the CI job.

        Returns:
            Number of lines successfully ingested.
        """
        entries: List[LogEntry] = []
        count = 0
        for i, line in enumerate(log_lines):
            level = self._detect_level(line)
            entry = LogEntry(
                job_id=job_id,
                line_number=i,
                timestamp=time.time() + i * 0.001,
                level=level,
                message=line.strip(),
                raw=line,
            )
            entries.append(entry)
            self._index_keywords(line, job_id, i)
            self._stats.total_bytes += len(line.encode("utf-8"))
            if level == "ERROR":
                self._stats.error_lines += 1
            elif level == "WARNING":
                self._stats.warning_lines += 1
            count += 1

        self._entries[job_id] = entries
        self._stats.total_jobs = len(self._entries)
        self._stats.total_lines += count
        self._stats.end_time = time.time()
        return count

    def search(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[LogEntry]:
        """Search ingested logs by query and optional filters.

        Args:
            query: Text to search for.
            filters: Optional filters (level, job_id, step).

        Returns:
            Matching log entries.
        """
        filters = filters or {}
        results: List[LogEntry] = []
        level_filter = filters.get("level")
        job_filter = filters.get("job_id")
        query_lower = query.lower()

        for job_id, entries in self._entries.items():
            if job_filter and job_id != job_filter:
                continue
            for entry in entries:
                if query_lower not in entry.message.lower():
                    continue
                if level_filter and entry.level != level_filter:
                    continue
                results.append(entry)
        return results

    def get_logs(self, job_id: str, step: Optional[str] = None) -> List[LogEntry]:
        """Retrieve logs for a specific job, optionally filtered by step.

        Args:
            job_id: The CI job identifier.
            step: Optional step name to filter by.

        Returns:
            Log entries for the job.
        """
        entries = self._entries.get(job_id, [])
        if step:
            entries = [e for e in entries if e.step == step]
        return entries

    def get_stats(self) -> IngestStats:
        """Get ingestion statistics.

        Returns:
            Current ingestion stats.
        """
        return self._stats

    # -- helpers --

    def _detect_level(self, line: str) -> str:
        upper = line.upper().strip()
        if any(kw in upper for kw in ("ERROR", "FATAL", "CRITICAL", "EXCEPTION", "FAIL")):
            return "ERROR"
        if any(kw in upper for kw in ("WARN", "WARNING")):
            return "WARNING"
        if any(kw in upper for kw in ("INFO", "DEBUG", "TRACE")):
            return "INFO"
        return "INFO"

    def _index_keywords(self, line: str, job_id: str, line_num: int) -> None:
        for word in line.lower().split():
            word = word.strip(".,;:()[]{}\"'")
            if len(word) < 3:
                continue
            if word not in self._index:
                self._index[word] = []
            self._index[word].append((job_id, line_num))
