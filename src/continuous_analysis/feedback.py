"""FeedbackLoop — Learn from diagnosis feedback."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class FeedbackEntry:
    """A feedback entry."""
    diagnosis_id: str
    category: str
    original_confidence: float
    outcome: str  # 'correct', 'incorrect', 'partial'
    timestamp: float = 0.0


@dataclass
class FeedbackStats:
    """Statistics about feedback."""
    total_feedback: int
    correct_count: int
    incorrect_count: int
    partial_count: int
    accuracy: float
    by_category: Dict[str, float]


class FeedbackLoop:
    """Learn from feedback on diagnoses.

    Records feedback, computes accuracy metrics, and
    adjusts internal weights for improved future diagnoses.
    """

    def __init__(self) -> None:
        self._feedback: List[FeedbackEntry] = []
        self._weights: Dict[str, float] = {}  # category -> weight
        self._category_correct: Dict[str, int] = {}
        self._category_total: Dict[str, int] = {}

    def record_feedback(self, diagnosis_id: str, category: str,
                        confidence: float, outcome: str) -> None:
        """Record feedback on a diagnosis.

        Args:
            diagnosis_id: Diagnosis identifier.
            category: Diagnosis category.
            confidence: Original confidence.
            outcome: 'correct', 'incorrect', or 'partial'.
        """
        entry = FeedbackEntry(
            diagnosis_id=diagnosis_id,
            category=category,
            original_confidence=confidence,
            outcome=outcome,
        )
        self._feedback.append(entry)

        # Update category stats
        if category not in self._category_total:
            self._category_total[category] = 0
            self._category_correct[category] = 0
        self._category_total[category] += 1
        if outcome == "correct":
            self._category_correct[category] += 1

    def compute_accuracy(self) -> float:
        """Compute overall diagnosis accuracy.

        Returns:
            Accuracy (0.0 to 1.0).
        """
        if not self._feedback:
            return 0.0
        correct = sum(1 for f in self._feedback if f.outcome == "correct")
        partial = sum(1 for f in self._feedback if f.outcome == "partial") * 0.5
        return (correct + partial) / len(self._feedback)

    def retrain_weights(self) -> Dict[str, float]:
        """Retrain category weights based on feedback.

        Returns:
            Updated weights by category.
        """
        for cat, total in self._category_total.items():
            correct = self._category_correct.get(cat, 0)
            accuracy = correct / total if total > 0 else 0.5
            # Weight = accuracy * confidence boost
            self._weights[cat] = 0.5 + accuracy * 0.5
        return dict(self._weights)

    def get_feedback_stats(self) -> FeedbackStats:
        """Get comprehensive feedback statistics.

        Returns:
            FeedbackStats with all metrics.
        """
        if not self._feedback:
            return FeedbackStats(
                total_feedback=0, correct_count=0, incorrect_count=0,
                partial_count=0, accuracy=0.0, by_category={},
            )

        correct = sum(1 for f in self._feedback if f.outcome == "correct")
        incorrect = sum(1 for f in self._feedback if f.outcome == "incorrect")
        partial = sum(1 for f in self._feedback if f.outcome == "partial")

        by_category: Dict[str, float] = {}
        for cat in self._category_total:
            total = self._category_total[cat]
            correct_c = self._category_correct.get(cat, 0)
            by_category[cat] = correct_c / total if total else 0.0

        return FeedbackStats(
            total_feedback=len(self._feedback),
            correct_count=correct,
            incorrect_count=incorrect,
            partial_count=partial,
            accuracy=self.compute_accuracy(),
            by_category=by_category,
        )

    def get_weight(self, category: str) -> float:
        """Get the weight for a category."""
        return self._weights.get(category, 0.5)

    def get_feedback_count(self) -> int:
        """Get total feedback entries."""
        return len(self._feedback)
