"""ReliabilityScorer — Score CI reliability."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class ComponentScore:
    """Reliability score for a component."""
    component: str
    score: float  # 0-100
    availability: float
    latency_p95: float
    error_rate: float


@dataclass
class Risk:
    """A reliability risk."""
    component: str
    risk_type: str
    severity: str  # 'low', 'medium', 'high', 'critical'
    description: str


@dataclass
class Mitigation:
    """A mitigation for a risk."""
    risk_type: str
    action: str
    estimated_impact: float


class ReliabilityScorer:
    """Score CI reliability across components.

    Aggregates metrics into reliability scores, identifies risks,
    and suggests mitigations.
    """

    def __init__(self) -> None:
        self._scores: Dict[str, ComponentScore] = {}
        self._history: Dict[str, List[float]] = {}  # component -> score history

    def compute_score(self, component: str, availability: float = 1.0,
                      latency_p95: float = 30.0, error_rate: float = 0.0) -> ComponentScore:
        """Compute reliability score for a component.

        Args:
            component: Component name.
            availability: Availability (0-1).
            latency_p95: P95 latency in seconds.
            error_rate: Error rate (0-1).

        Returns:
            ComponentScore.
        """
        # Score formula: weighted combination
        avail_score = availability * 50
        latency_score = max(0, 30 - (latency_p95 / 10))  # penalty for high latency
        error_score = (1 - error_rate) * 20

        score = min(100, avail_score + latency_score + error_score)

        cs = ComponentScore(
            component=component,
            score=score,
            availability=availability,
            latency_p95=latency_p95,
            error_rate=error_rate,
        )
        self._scores[component] = cs
        if component not in self._history:
            self._history[component] = []
        self._history[component].append(score)
        return cs

    def get_reliability_trend(self, component: Optional[str] = None) -> Dict[str, List[float]]:
        """Get reliability score trends.

        Args:
            component: Optional specific component.

        Returns:
            Dict of component -> score history.
        """
        if component:
            return {component: self._history.get(component, [])}
        return dict(self._history)

    def identify_risks(self) -> List[Risk]:
        """Identify reliability risks.

        Returns:
            List of identified risks.
        """
        risks: List[Risk] = []
        for name, score in self._scores.items():
            if score.availability < 0.99:
                risks.append(Risk(
                    component=name, risk_type="availability",
                    severity="high" if score.availability < 0.95 else "medium",
                    description=f"Availability {score.availability:.2%} below 99%",
                ))
            if score.error_rate > 0.05:
                risks.append(Risk(
                    component=name, risk_type="error_rate",
                    severity="critical" if score.error_rate > 0.1 else "high",
                    description=f"Error rate {score.error_rate:.2%} above 5%",
                ))
            if score.latency_p95 > 60:
                risks.append(Risk(
                    component=name, risk_type="latency",
                    severity="medium",
                    description=f"P95 latency {score.latency_p95:.0f}s exceeds 60s target",
                ))
        return risks

    def suggest_mitigations(self, risks: List[Risk]) -> List[Mitigation]:
        """Suggest mitigations for identified risks.

        Args:
            risks: Risks to mitigate.

        Returns:
            List of suggested mitigations.
        """
        mitigations: List[Mitigation] = []
        for risk in risks:
            if risk.risk_type == "availability":
                mitigations.append(Mitigation(
                    risk_type="availability",
                    action="Add redundancy and failover mechanisms",
                    estimated_impact=0.1,
                ))
            elif risk.risk_type == "error_rate":
                mitigations.append(Mitigation(
                    risk_type="error_rate",
                    action="Implement retry logic and circuit breakers",
                    estimated_impact=0.15,
                ))
            elif risk.risk_type == "latency":
                mitigations.append(Mitigation(
                    risk_type="latency",
                    action="Optimize hot paths and add caching",
                    estimated_impact=0.2,
                ))
        return mitigations

    def get_overall_score(self) -> float:
        """Get average reliability score across all components."""
        if not self._scores:
            return 0.0
        return sum(s.score for s in self._scores.values()) / len(self._scores)
