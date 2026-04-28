"""DiagnosisEngine — Orchestrate diagnosis pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Dict, List, Optional

from .diagnostician import Diagnosis, Failure


@dataclass
class AnalyzerResult:
    """Result from a single analyzer."""
    analyzer_name: str
    category: str
    confidence: float
    details: str


@dataclass
class DiagnosisReport:
    """Full diagnosis report from all analyzers."""
    failure_id: str
    results: List[AnalyzerResult]
    final_diagnosis: Optional[Diagnosis]
    consensus_confidence: float
    feedback_applied: bool = False


class DiagnosisEngine:
    """Orchestrate multiple analyzers for comprehensive diagnosis.

    Registers analyzers, runs them in sequence, and combines
    their results into a consensus diagnosis.
    """

    def __init__(self) -> None:
        self._analyzers: Dict[str, Callable] = {}
        self._feedback: List[Dict] = []

    def register_analyzer(self, name: str, analyzer: Callable) -> None:
        """Register an analyzer function.

        Args:
            name: Analyzer name.
            analyzer: Callable that takes (failure) -> AnalyzerResult.
        """
        self._analyzers[name] = analyzer

    def run_diagnosis(self, failure: Failure) -> DiagnosisReport:
        """Run all registered analyzers on a failure.

        Args:
            failure: The failure to diagnose.

        Returns:
            Comprehensive DiagnosisReport.
        """
        results: List[AnalyzerResult] = []
        for name, analyzer in self._analyzers.items():
            try:
                result = analyzer(failure)
                results.append(result)
            except Exception as e:
                results.append(AnalyzerResult(
                    analyzer_name=name,
                    category="error",
                    confidence=0.0,
                    details=str(e),
                ))

        # Compute consensus
        if results:
            avg_confidence = sum(r.confidence for r in results) / len(results)
            # Pick best result as final
            best = max(results, key=lambda r: r.confidence)
            final = Diagnosis(
                failure_id=failure.id,
                root_cause=best.details,
                category=best.category,
                confidence=avg_confidence,
                explanation=f"Consensus from {len(results)} analyzers",
                suggested_fix="See analyzer details",
            )
        else:
            avg_confidence = 0.0
            final = None

        return DiagnosisReport(
            failure_id=failure.id,
            results=results,
            final_diagnosis=final,
            consensus_confidence=avg_confidence,
        )

    def get_diagnosis_report(self, failure: Failure) -> DiagnosisReport:
        """Get a full diagnosis report for a failure.

        Args:
            failure: The failure.

        Returns:
            DiagnosisReport.
        """
        return self.run_diagnosis(failure)

    def learn_from_feedback(self, diagnosis: Diagnosis, feedback: str) -> None:
        """Learn from user feedback on a diagnosis.

        Args:
            diagnosis: The original diagnosis.
            feedback: User feedback (correct/incorrect/helpful).
        """
        self._feedback.append({
            "failure_id": diagnosis.failure_id,
            "category": diagnosis.category,
            "original_confidence": diagnosis.confidence,
            "feedback": feedback,
        })

    def get_feedback_count(self) -> int:
        """Get total feedback entries."""
        return len(self._feedback)
