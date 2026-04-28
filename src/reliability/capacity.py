"""CapacityPlanner — Plan CI capacity and forecast demand."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class DemandForecast:
    """Forecasted CI demand."""
    day: int
    predicted_jobs: int
    predicted_runners: int
    confidence: float


@dataclass
class CapacityInfo:
    """Current CI capacity."""
    total_runners: int
    active_runners: int
    idle_runners: int
    utilization: float
    max_parallel_jobs: int


@dataclass
class ScalingSuggestion:
    """Suggestion for scaling CI capacity."""
    action: str  # 'scale_up', 'scale_down', 'maintain'
    runners_to_add: int
    estimated_cost_change: float
    reason: str


@dataclass
class CostEstimate:
    """Cost estimate for a capacity configuration."""
    runners: int
    hourly_cost: float
    monthly_cost: float
    cost_per_job: float


class CapacityPlanner:
    """Plan CI capacity based on demand forecasts.

    Forecasts job demand, tracks current capacity,
    and suggests scaling actions.
    """

    def __init__(self) -> None:
        self._capacity = CapacityInfo(
            total_runners=20, active_runners=15, idle_runners=5,
            utilization=0.75, max_parallel_jobs=20,
        )
        self._job_history: List[Tuple[int, int]] = []  # (day, job_count)
        self._cost_per_runner_hour = 0.10  # $0.10/runner/hour

    def forecast_demand(self, days: int = 7) -> List[DemandForecast]:
        """Forecast CI demand for upcoming days.

        Args:
            days: Number of days to forecast.

        Returns:
            List of DemandForecast for each day.
        """
        if not self._job_history:
            # Default: steady state at current capacity
            return [
                DemandForecast(
                    day=i,
                    predicted_jobs=self._capacity.total_runners * 100,
                    predicted_runners=self._capacity.total_runners,
                    confidence=0.5,
                )
                for i in range(days)
            ]

        # Simple linear extrapolation
        recent_counts = [count for _, count in self._job_history[-7:]]
        avg_daily = sum(recent_counts) / len(recent_counts) if recent_counts else 1000
        growth_rate = 1.0
        if len(recent_counts) >= 2:
            growth_rate = recent_counts[-1] / max(recent_counts[0], 1)

        forecasts: List[DemandForecast] = []
        for i in range(days):
            predicted = int(avg_daily * (growth_rate ** (i / 7)))
            runners_needed = max(1, predicted // 100)
            confidence = max(0.3, 0.8 - i * 0.05)
            forecasts.append(DemandForecast(
                day=i,
                predicted_jobs=predicted,
                predicted_runners=runners_needed,
                confidence=confidence,
            ))
        return forecasts

    def get_current_capacity(self) -> CapacityInfo:
        """Get current capacity information.

        Returns:
            Current CapacityInfo.
        """
        return self._capacity

    def suggest_scaling(self, demand: Optional[List[DemandForecast]] = None) -> ScalingSuggestion:
        """Suggest scaling action based on demand.

        Args:
            demand: Optional demand forecast.

        Returns:
            ScalingSuggestion.
        """
        if demand is None:
            demand = self.forecast_demand(1)

        peak = max(d.predicted_runners for d in demand)
        current = self._capacity.total_runners

        if peak > current * 1.2:
            add = peak - current
            return ScalingSuggestion(
                action="scale_up",
                runners_to_add=add,
                estimated_cost_change=add * self._cost_per_runner_hour * 24 * 30,
                reason=f"Peak demand requires {peak} runners, have {current}",
            )
        elif peak < current * 0.6:
            remove = current - peak
            return ScalingSuggestion(
                action="scale_down",
                runners_to_add=-remove,
                estimated_cost_change=-remove * self._cost_per_runner_hour * 24 * 30,
                reason=f"Capacity underutilized, can reduce to {peak}",
            )
        else:
            return ScalingSuggestion(
                action="maintain",
                runners_to_add=0,
                estimated_cost_change=0.0,
                reason="Current capacity meets demand",
            )

    def estimate_cost(self, runners: int, hours: int = 730) -> CostEstimate:
        """Estimate cost for a capacity configuration.

        Args:
            runners: Number of runners.
            hours: Hours in period (default 730 = ~1 month).

        Returns:
            CostEstimate.
        """
        hourly = runners * self._cost_per_runner_hour
        monthly = hourly * hours
        jobs_per_month = runners * 100 * 30  # rough estimate
        cost_per_job = monthly / max(jobs_per_month, 1)

        return CostEstimate(
            runners=runners,
            hourly_cost=hourly,
            monthly_cost=monthly,
            cost_per_job=cost_per_job,
        )

    def record_jobs(self, day: int, count: int) -> None:
        """Record job count for a day."""
        self._job_history.append((day, count))

    def set_capacity(self, capacity: CapacityInfo) -> None:
        """Set current capacity info."""
        self._capacity = capacity
