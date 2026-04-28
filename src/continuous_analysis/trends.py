"""TrendAnalyzer — Analyze CI trends and anomalies."""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class TrendResult:
    """Result of trend analysis."""
    metric: str
    direction: str  # 'up', 'down', 'flat'
    magnitude: float
    confidence: float
    data_points: int


@dataclass
class Anomaly:
    """Detected anomaly."""
    metric: str
    value: float
    expected: float
    deviation: float
    severity: str  # 'low', 'medium', 'high'


@dataclass
class ForecastPoint:
    """A forecasted data point."""
    day: int
    value: float
    lower_bound: float
    upper_bound: float


class TrendAnalyzer:
    """Analyze CI metric trends and detect anomalies.

    Tracks metrics over time, identifies trends, detects
    anomalies, and generates forecasts.
    """

    def __init__(self) -> None:
        self._metrics: Dict[str, List[float]] = {}

    def record(self, metric: str, value: float) -> None:
        """Record a metric value."""
        if metric not in self._metrics:
            self._metrics[metric] = []
        self._metrics[metric].append(value)

    def analyze_trend(self, metric: str, period: str = "7d") -> Optional[TrendResult]:
        """Analyze trend for a metric.

        Args:
            metric: Metric name.
            period: Analysis period.

        Returns:
            TrendResult or None.
        """
        values = self._metrics.get(metric, [])
        if len(values) < 2:
            return TrendResult(metric=metric, direction="flat", magnitude=0.0,
                               confidence=0.0, data_points=len(values))

        # Simple linear regression
        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n

        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))

        slope = numerator / denominator if denominator else 0
        magnitude = abs(slope)

        # Direction
        if abs(slope) < 0.01 * y_mean if y_mean != 0 else abs(slope) < 0.01:
            direction = "flat"
        elif slope > 0:
            direction = "up"
        else:
            direction = "down"

        # Confidence based on R-squared
        ss_res = sum((v - (y_mean + slope * (i - x_mean))) ** 2 for i, v in enumerate(values))
        ss_tot = sum((v - y_mean) ** 2 for v in values)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot else 0
        confidence = max(0, min(1, r_squared))

        return TrendResult(
            metric=metric, direction=direction, magnitude=magnitude,
            confidence=confidence, data_points=n,
        )

    def detect_anomalies(self, metric: str, threshold: float = 2.0) -> List[Anomaly]:
        """Detect anomalies in a metric using z-score.

        Args:
            metric: Metric to analyze.
            threshold: Z-score threshold for anomaly detection.

        Returns:
            List of detected Anomalies.
        """
        values = self._metrics.get(metric, [])
        if len(values) < 3:
            return []

        mean = sum(values) / len(values)
        std = math.sqrt(sum((v - mean) ** 2 for v in values) / len(values))
        if std == 0:
            return []

        anomalies: List[Anomaly] = []
        for v in values:
            z = abs(v - mean) / std
            if z > threshold:
                severity = "high" if z > 3 else ("medium" if z > 2.5 else "low")
                anomalies.append(Anomaly(
                    metric=metric, value=v, expected=mean,
                    deviation=z, severity=severity,
                ))
        return anomalies

    def forecast(self, metric: str, days: int = 7) -> List[ForecastPoint]:
        """Forecast metric values.

        Args:
            metric: Metric to forecast.
            days: Days to forecast.

        Returns:
            List of ForecastPoint.
        """
        values = self._metrics.get(metric, [])
        if len(values) < 2:
            return [ForecastPoint(day=i, value=0, lower_bound=0, upper_bound=0) for i in range(days)]

        n = len(values)
        x_mean = (n - 1) / 2
        y_mean = sum(values) / n

        numerator = sum((i - x_mean) * (v - y_mean) for i, v in enumerate(values))
        denominator = sum((i - x_mean) ** 2 for i in range(n))
        slope = numerator / denominator if denominator else 0
        intercept = y_mean - slope * x_mean

        std = math.sqrt(sum((v - y_mean) ** 2 for v in values) / max(n, 1))

        forecasts: List[ForecastPoint] = []
        for i in range(days):
            x = n + i
            value = intercept + slope * x
            forecasts.append(ForecastPoint(
                day=i,
                value=value,
                lower_bound=value - 2 * std,
                upper_bound=value + 2 * std,
            ))
        return forecasts

    def correlate_trends(self, metrics: List[str]) -> Dict[str, float]:
        """Compute correlation between metric trends.

        Args:
            metrics: Metrics to correlate.

        Returns:
            Dict of "metric1:metric2" -> correlation coefficient.
        """
        result: Dict[str, float] = {}
        for i in range(len(metrics)):
            for j in range(i + 1, len(metrics)):
                v1 = self._metrics.get(metrics[i], [])
                v2 = self._metrics.get(metrics[j], [])
                if len(v1) < 3 or len(v2) < 3:
                    continue
                min_len = min(len(v1), len(v2))
                v1 = v1[:min_len]
                v2 = v2[:min_len]

                m1 = sum(v1) / len(v1)
                m2 = sum(v2) / len(v2)
                cov = sum((a - m1) * (b - m2) for a, b in zip(v1, v2)) / len(v1)
                s1 = math.sqrt(sum((a - m1) ** 2 for a in v1) / len(v1))
                s2 = math.sqrt(sum((b - m2) ** 2 for b in v2) / len(v2))

                corr = cov / (s1 * s2) if s1 and s2 else 0
                key = f"{metrics[i]}:{metrics[j]}"
                result[key] = corr
        return result
