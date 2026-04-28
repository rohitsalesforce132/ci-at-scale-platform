"""HealthMonitor — Monitor overall CI health."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class HealthScore:
    """Overall CI health score."""
    score: float  # 0-100
    status: str  # 'healthy', 'degraded', 'unhealthy', 'critical'
    components: Dict[str, float] = field(default_factory=dict)


@dataclass
class DegradingArea:
    """A degrading area of CI."""
    area: str
    current_score: float
    previous_score: float
    trend: str  # 'declining', 'stable', 'improving'


@dataclass
class FailurePrediction:
    """Predicted failure."""
    component: str
    probability: float
    horizon_hours: int
    reason: str


@dataclass
class DashboardData:
    """Data for CI health dashboard."""
    health_score: float
    active_runs: int
    failure_rate: float
    avg_duration: float
    queue_depth: int
    degrading_areas: List[DegradingArea]


class HealthMonitor:
    """Monitor overall CI health across all subsystems.

    Aggregates metrics into a health score, identifies
    degrading areas, and predicts potential failures.
    """

    def __init__(self) -> None:
        self._metrics: Dict[str, List[float]] = {}
        self._component_scores: Dict[str, float] = {}

    def record_metric(self, name: str, value: float) -> None:
        """Record a metric value.

        Args:
            name: Metric name.
            value: Metric value.
        """
        if name not in self._metrics:
            self._metrics[name] = []
        self._metrics[name].append(value)

    def set_component_score(self, component: str, score: float) -> None:
        """Set health score for a component."""
        self._component_scores[component] = score

    def get_health_score(self) -> HealthScore:
        """Get overall CI health score.

        Returns:
            HealthScore with assessment.
        """
        if not self._component_scores:
            return HealthScore(score=100.0, status="healthy", components={})

        avg = sum(self._component_scores.values()) / len(self._component_scores)
        if avg >= 90:
            status = "healthy"
        elif avg >= 70:
            status = "degraded"
        elif avg >= 50:
            status = "unhealthy"
        else:
            status = "critical"

        return HealthScore(
            score=avg,
            status=status,
            components=dict(self._component_scores),
        )

    def get_degrading_areas(self) -> List[DegradingArea]:
        """Identify degrading areas of CI.

        Returns:
            List of DegradingArea.
        """
        areas: List[DegradingArea] = []
        for name, values in self._metrics.items():
            if len(values) < 2:
                continue
            current = values[-1]
            previous = values[-2]
            if current < previous:
                trend = "declining"
            elif current > previous:
                trend = "improving"
            else:
                trend = "stable"

            if trend == "declining":
                areas.append(DegradingArea(
                    area=name,
                    current_score=current,
                    previous_score=previous,
                    trend=trend,
                ))
        return areas

    def predict_failures(self, horizon_hours: int = 24) -> List[FailurePrediction]:
        """Predict potential failures.

        Args:
            horizon_hours: Prediction horizon.

        Returns:
            List of FailurePrediction.
        """
        predictions: List[FailurePrediction] = []
        for name, values in self._metrics.items():
            if len(values) < 3:
                continue
            # Simple trend: if last 3 values are declining or rapidly increasing
            recent = values[-3:]
            # Declining trend (lower scores = worse)
            declining = all(recent[i] > recent[i + 1] for i in range(len(recent) - 1))
            # Rising trend (for metrics where up is bad, like error rate)
            rising = all(recent[i] < recent[i + 1] for i in range(len(recent) - 1))
            if declining or rising:
                if declining:
                    decline_rate = (recent[0] - recent[-1]) / max(recent[0], 0.01)
                else:
                    decline_rate = (recent[-1] - recent[0]) / max(recent[0], 0.01)
                probability = min(0.95, decline_rate * 5)
                if probability > 0.2:
                    predictions.append(FailurePrediction(
                        component=name,
                        probability=probability,
                        horizon_hours=horizon_hours,
                        reason=f"{'Rising' if rising else 'Declining'} trend: {recent[0]:.2f} → {recent[-1]:.2f}",
                    ))
        return predictions

    def get_dashboard_data(self) -> DashboardData:
        """Get data for CI health dashboard.

        Returns:
            DashboardData with key metrics.
        """
        health = self.get_health_score()
        failure_rate = self._component_scores.get("failure_rate", 0.05)
        avg_duration = self._component_scores.get("avg_duration", 120.0)
        active_runs = int(self._component_scores.get("active_runs", 0))
        queue_depth = int(self._component_scores.get("queue_depth", 0))

        return DashboardData(
            health_score=health.score,
            active_runs=active_runs,
            failure_rate=failure_rate,
            avg_duration=avg_duration,
            queue_depth=queue_depth,
            degrading_areas=self.get_degrading_areas(),
        )
