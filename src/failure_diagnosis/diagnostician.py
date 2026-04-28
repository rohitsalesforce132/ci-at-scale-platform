"""FailureDiagnostician — Diagnose CI failures."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class Diagnosis:
    """Result of diagnosing a failure."""
    failure_id: str
    root_cause: str
    category: str
    confidence: float
    explanation: str
    suggested_fix: str
    related_failures: List[str] = field(default_factory=list)


@dataclass
class Failure:
    """A CI failure."""
    id: str
    test_name: str
    error_message: str
    job_id: str = ""
    commit: str = ""
    timestamp: float = 0.0


class FailureDiagnostician:
    """Diagnose CI failures using pattern matching and heuristics.

    Categorizes failures, identifies root causes, and generates
    explanations with confidence scores.
    """

    _CATEGORIES = {
        "timeout": ["timeout", "timed out", "deadline exceeded"],
        "network": ["connection refused", "connection reset", "dns", "network"],
        "build": ["compilation error", "build failed", "syntax error"],
        "test": ["assertion", "expected", "assertionerror"],
        "resource": ["out of memory", "oom", "disk full", "resource exhausted"],
        "dependency": ["import error", "module not found", "no module named", "dependency"],
        "permission": ["permission denied", "access denied", "unauthorized"],
        "configuration": ["config", "environment", "env var", "missing"],
    }

    def diagnose(self, failure: Failure, logs: Optional[List[str]] = None) -> Diagnosis:
        """Diagnose a CI failure.

        Args:
            failure: The failure to diagnose.
            logs: Optional associated logs.

        Returns:
            Diagnosis with root cause and suggestions.
        """
        category = self._classify(failure.error_message)
        root_cause = self._identify_root_cause(failure, logs or [])
        confidence = self._compute_confidence(failure, category)
        explanation = self._generate_explanation(failure, category, root_cause)
        fix = self._suggest_fix(category, root_cause)

        return Diagnosis(
            failure_id=failure.id,
            root_cause=root_cause,
            category=category,
            confidence=confidence,
            explanation=explanation,
            suggested_fix=fix,
        )

    def get_confidence(self, diagnosis: Diagnosis) -> float:
        """Get confidence score for a diagnosis.

        Args:
            diagnosis: The diagnosis.

        Returns:
            Confidence score (0.0 to 1.0).
        """
        return diagnosis.confidence

    def explain(self, diagnosis: Diagnosis) -> str:
        """Get human-readable explanation of a diagnosis.

        Args:
            diagnosis: The diagnosis.

        Returns:
            Explanation string.
        """
        return diagnosis.explanation

    def suggest_fix(self, diagnosis: Diagnosis) -> str:
        """Get fix suggestion from a diagnosis.

        Args:
            diagnosis: The diagnosis.

        Returns:
            Fix suggestion.
        """
        return diagnosis.suggested_fix

    # -- helpers --

    def _classify(self, message: str) -> str:
        lower = message.lower()
        for cat, keywords in self._CATEGORIES.items():
            if any(kw in lower for kw in keywords):
                return cat
        return "unknown"

    def _identify_root_cause(self, failure: Failure, logs: List[str]) -> str:
        error_lower = failure.error_message.lower()
        if "timeout" in error_lower:
            return "Operation exceeded time limit"
        if "connection" in error_lower:
            return "Network connectivity issue"
        if "import" in error_lower or "module" in error_lower:
            return "Missing or incompatible dependency"
        if "assertion" in error_lower:
            return "Test assertion failed — expected behavior changed"
        if "memory" in error_lower:
            return "Insufficient memory resources"
        # Check logs for clues
        for line in logs[-5:]:
            if "killed" in line.lower():
                return "Process killed (likely OOM)"
        return failure.error_message[:200]

    def _compute_confidence(self, failure: Failure, category: str) -> float:
        if category == "unknown":
            return 0.3
        # More specific error messages → higher confidence
        msg_len = len(failure.error_message)
        base = 0.5
        if msg_len > 50:
            base += 0.1
        if msg_len > 100:
            base += 0.1
        if any(kw in failure.error_message.lower() for kw in ("error", "exception", "failed")):
            base += 0.15
        return min(0.95, base)

    def _generate_explanation(self, failure: Failure, category: str, root_cause: str) -> str:
        return f"[{category.upper()}] {failure.test_name}: {root_cause}. Error: {failure.error_message[:100]}"

    def _suggest_fix(self, category: str, root_cause: str) -> str:
        _FIXES = {
            "timeout": "Increase timeout or optimize the slow operation",
            "network": "Check network connectivity and retry with backoff",
            "build": "Fix compilation errors and update build configuration",
            "test": "Review assertion — expected values may need updating",
            "resource": "Increase resource limits or optimize memory usage",
            "dependency": "Install missing dependencies or pin versions",
            "permission": "Check access permissions and credentials",
            "configuration": "Verify environment variables and config files",
        }
        return _FIXES.get(category, "Investigate the error logs for more details")
