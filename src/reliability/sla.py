"""SLATracker — Track CI SLA compliance."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class SLADefinition:
    """Definition of an SLA."""
    name: str
    target: float  # e.g. 0.999 for 99.9%
    metric: str = "availability"  # availability, latency, mttr
    window_hours: int = 720  # 30 days default


@dataclass
class SLACheckResult:
    """Result of checking an SLA."""
    name: str
    target: float
    actual: float
    compliant: bool
    breaches: int
    period: str


@dataclass
class SLAReport:
    """SLA report for a period."""
    period: str
    sla_results: List[SLACheckResult]
    overall_compliance: float
    total_breaches: int


class SLATracker:
    """Track CI SLA compliance.

    Defines SLAs, records measurements, and reports
    on compliance over configurable periods.
    """

    def __init__(self) -> None:
        self._slas: Dict[str, SLADefinition] = {}
        self._measurements: Dict[str, List[Tuple[float, float]]] = {}  # sla_name -> [(timestamp, value)]

    def define_sla(self, name: str, target: float, metric: str = "availability") -> SLADefinition:
        """Define an SLA.

        Args:
            name: SLA name.
            target: Target value (e.g. 0.999 for 99.9%).
            metric: Metric type.

        Returns:
            Created SLADefinition.
        """
        sla = SLADefinition(name=name, target=target, metric=metric)
        self._slas[name] = sla
        self._measurements[name] = []
        return sla

    def record_measurement(self, sla_name: str, value: float) -> None:
        """Record an SLA measurement.

        Args:
            sla_name: SLA name.
            value: Measured value.
        """
        if sla_name not in self._measurements:
            self._measurements[sla_name] = []
        self._measurements[sla_name].append((time.time(), value))

    def check_sla(self, name: str) -> Optional[SLACheckResult]:
        """Check current SLA compliance.

        Args:
            name: SLA name.

        Returns:
            SLACheckResult or None if SLA not defined.
        """
        sla = self._slas.get(name)
        if not sla:
            return None

        measurements = self._measurements.get(name, [])
        if not measurements:
            return SLACheckResult(name=name, target=sla.target, actual=0.0,
                                  compliant=False, breaches=0, period="30d")

        actual = sum(v for _, v in measurements) / len(measurements)
        breaches = sum(1 for _, v in measurements if v < sla.target)

        return SLACheckResult(
            name=name,
            target=sla.target,
            actual=actual,
            compliant=actual >= sla.target,
            breaches=breaches,
            period=f"{sla.window_hours}h",
        )

    def get_sla_report(self, period: str = "30d") -> SLAReport:
        """Get SLA report for a period.

        Args:
            period: Report period.

        Returns:
            SLAReport with all SLA results.
        """
        results: List[SLACheckResult] = []
        for name in self._slas:
            check = self.check_sla(name)
            if check:
                results.append(check)

        total_breaches = sum(r.breaches for r in results)
        compliant_count = sum(1 for r in results if r.compliant)
        overall = compliant_count / len(results) if results else 0.0

        return SLAReport(
            period=period,
            sla_results=results,
            overall_compliance=overall,
            total_breaches=total_breaches,
        )

    def compute_breach_rate(self, name: str) -> float:
        """Compute breach rate for an SLA.

        Args:
            name: SLA name.

        Returns:
            Breach rate (0.0 to 1.0).
        """
        measurements = self._measurements.get(name, [])
        if not measurements:
            return 0.0
        sla = self._slas.get(name)
        if not sla:
            return 0.0
        breaches = sum(1 for _, v in measurements if v < sla.target)
        return breaches / len(measurements)
