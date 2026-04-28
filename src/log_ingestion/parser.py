"""LogParser — Parse structured/unstructured CI logs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple


@dataclass
class ParsedLine:
    """Result of parsing a single log line."""
    level: str
    timestamp: Optional[str]
    module: Optional[str]
    message: str
    is_error: bool
    raw: str


@dataclass
class ErrorContext:
    """Context around an error in logs."""
    error_line: str
    before: List[str]
    after: List[str]
    error_type: Optional[str]
    line_number: int


class LogParser:
    """Parse structured and unstructured CI log lines.

    Supports common CI log formats including GitHub Actions,
    Jenkins, and generic structured logging.
    """

    # Patterns for structured log lines
    _PATTERNS = [
        # ISO timestamp + level
        re.compile(
            r"(?P<ts>\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}(?:\.\d+)?)\s*"
            r"(?P<level>ERROR|WARN|INFO|DEBUG|FATAL|CRITICAL)\s*"
            r"(?:\[(?P<module>[^\]]*)\])?\s*"
            r"(?P<message>.*)",
            re.IGNORECASE,
        ),
        # [level] message
        re.compile(
            r"\[(?P<level>ERROR|WARN(?:ING)?|INFO|DEBUG|FATAL|CRITICAL)\]\s*(?P<message>.*)",
            re.IGNORECASE,
        ),
    ]

    _LEVEL_MAP: Dict[str, str] = {
        "WARN": "WARNING",
        "WARNING": "WARNING",
        "ERR": "ERROR",
        "ERROR": "ERROR",
        "FATAL": "ERROR",
        "CRITICAL": "ERROR",
        "INFO": "INFO",
        "DEBUG": "DEBUG",
    }

    def parse_line(self, line: str) -> ParsedLine:
        """Parse a single log line into structured components.

        Args:
            line: Raw log line.

        Returns:
            ParsedLine with extracted fields.
        """
        for pattern in self._PATTERNS:
            m = pattern.match(line.strip())
            if m:
                groups = m.groupdict()
                raw_level = (groups.get("level") or "INFO").upper()
                level = self._LEVEL_MAP.get(raw_level, raw_level)
                return ParsedLine(
                    level=level,
                    timestamp=groups.get("ts"),
                    module=groups.get("module"),
                    message=groups.get("message", line).strip(),
                    is_error=level in ("ERROR", "FATAL"),
                    raw=line,
                )

        # Unstructured fallback
        level = self._classify_unstructured(line)
        return ParsedLine(
            level=level,
            timestamp=None,
            module=None,
            message=line.strip(),
            is_error=level == "ERROR",
            raw=line,
        )

    def extract_error_context(self, lines: List[str], context_size: int = 3) -> List[ErrorContext]:
        """Extract error context from a list of log lines.

        Args:
            lines: All log lines.
            context_size: Number of lines before/after error.

        Returns:
            List of ErrorContext for each error found.
        """
        contexts: List[ErrorContext] = []
        for i, line in enumerate(lines):
            parsed = self.parse_line(line)
            if parsed.is_error:
                before = lines[max(0, i - context_size):i]
                after = lines[i + 1:min(len(lines), i + 1 + context_size)]
                error_type = self._extract_error_type(parsed.message)
                contexts.append(ErrorContext(
                    error_line=line,
                    before=before,
                    after=after,
                    error_type=error_type,
                    line_number=i,
                ))
        return contexts

    def classify_line(self, line: str) -> str:
        """Classify a log line by type.

        Args:
            line: Raw log line.

        Returns:
            Classification: 'error', 'warning', 'info', 'debug', 'command', or 'output'.
        """
        parsed = self.parse_line(line)
        if parsed.level == "ERROR":
            return "error"
        if parsed.level == "WARNING":
            return "warning"
        if parsed.level == "DEBUG":
            return "debug"
        stripped = line.strip()
        if stripped.startswith("$") or stripped.startswith(">"):
            return "command"
        if parsed.level == "INFO":
            return "info"
        return "output"

    def detect_patterns(self, lines: List[str]) -> List[Dict[str, str]]:
        """Detect common patterns in log lines.

        Args:
            lines: Log lines to analyze.

        Returns:
            List of detected patterns with type and description.
        """
        patterns: List[Dict[str, str]] = []
        parsed_lines = [self.parse_line(l) for l in lines]

        # Check for repeated errors
        error_msgs: Dict[str, int] = {}
        for p in parsed_lines:
            if p.is_error:
                key = p.message[:80]
                error_msgs[key] = error_msgs.get(key, 0) + 1

        for msg, count in error_msgs.items():
            if count > 1:
                patterns.append({
                    "type": "repeated_error",
                    "description": f"Error repeated {count} times: {msg[:60]}",
                })

        # Check for timeout patterns
        for line in lines:
            if "timeout" in line.lower() or "timed out" in line.lower():
                patterns.append({
                    "type": "timeout",
                    "description": f"Timeout detected: {line.strip()[:80]}",
                })
                break

        # Check for OOM patterns
        for line in lines:
            if "out of memory" in line.lower() or "oom" in line.lower():
                patterns.append({
                    "type": "oom",
                    "description": f"OOM detected: {line.strip()[:80]}",
                })
                break

        # Check for connection errors
        for line in lines:
            if "connection" in line.lower() and ("refused" in line.lower() or "reset" in line.lower()):
                patterns.append({
                    "type": "connection_error",
                    "description": f"Connection issue: {line.strip()[:80]}",
                })
                break

        return patterns

    # -- helpers --

    def _classify_unstructured(self, line: str) -> str:
        upper = line.upper()
        if any(kw in upper for kw in ("ERROR", "FAIL", "EXCEPTION", "FATAL", "CRITICAL", "TRACEBACK")):
            return "ERROR"
        if any(kw in upper for kw in ("WARN", "WARNING")):
            return "WARNING"
        return "INFO"

    def _extract_error_type(self, message: str) -> Optional[str]:
        match = re.search(r"(\w+Error|\w+Exception)", message)
        return match.group(1) if match else None
