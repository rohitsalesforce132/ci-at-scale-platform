"""EscalationManager — Manage failure escalation policies."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class EscalationPolicy:
    """Escalation policy configuration."""
    levels: List[str] = field(default_factory=lambda: ["engineer", "team_lead", "director"])
    timeout_minutes: List[int] = field(default_factory=lambda: [30, 60, 120])
    channels: List[str] = field(default_factory=lambda: ["slack", "slack", "pagerduty"])


@dataclass
class OncallSchedule:
    """On-call rotation schedule."""
    primary: str
    secondary: str
    start_time: float = 0.0
    end_time: float = 0.0


@dataclass
class EscalationRecord:
    """Record of an escalation."""
    failure_id: str
    level: int
    escalated_to: str
    timestamp: float
    acknowledged: bool = False


class EscalationManager:
    """Manage escalation of CI failures.

    Implements multi-level escalation policies with SLA tracking
    and on-call rotation support.
    """

    def __init__(self) -> None:
        self._policy = EscalationPolicy()
        self._oncall: Optional[OncallSchedule] = None
        self._escalations: List[EscalationRecord] = []
        self._sla_targets: Dict[str, float] = {}  # severity -> max_minutes

    def escalate(self, failure_id: str, level: int = 0) -> EscalationRecord:
        """Escalate a failure to a given level.

        Args:
            failure_id: The failure to escalate.
            level: Escalation level (0-indexed).

        Returns:
            EscalationRecord.
        """
        if level >= len(self._policy.levels):
            level = len(self._policy.levels) - 1

        target = self._policy.levels[level]
        if level == 0 and self._oncall:
            target = self._oncall.primary

        record = EscalationRecord(
            failure_id=failure_id,
            level=level,
            escalated_to=target,
            timestamp=time.time(),
        )
        self._escalations.append(record)
        return record

    def get_escalation_policy(self) -> EscalationPolicy:
        """Get the current escalation policy.

        Returns:
            Current EscalationPolicy.
        """
        return self._policy

    def set_oncall(self, schedule: OncallSchedule) -> None:
        """Set the on-call schedule.

        Args:
            schedule: On-call schedule to set.
        """
        self._oncall = schedule

    def check_sla(self, failure_id: str, failure_time: float) -> Dict[str, Any]:
        """Check if an SLA has been breached.

        Args:
            failure_id: The failure to check.
            failure_time: When the failure occurred.

        Returns:
            Dict with SLA check results.
        """
        elapsed = (time.time() - failure_time) / 60  # minutes
        acknowledged = any(
            e.failure_id == failure_id and e.acknowledged
            for e in self._escalations
        )

        max_minutes = 60  # default SLA
        breached = elapsed > max_minutes and not acknowledged

        return {
            "failure_id": failure_id,
            "elapsed_minutes": elapsed,
            "max_minutes": max_minutes,
            "breached": breached,
            "acknowledged": acknowledged,
        }

    def acknowledge(self, failure_id: str) -> bool:
        """Acknowledge a failure escalation.

        Args:
            failure_id: The failure to acknowledge.

        Returns:
            True if found and acknowledged.
        """
        for record in self._escalations:
            if record.failure_id == failure_id:
                record.acknowledged = True
                return True
        return False

    def get_escalations(self, failure_id: Optional[str] = None) -> List[EscalationRecord]:
        """Get escalation records."""
        if failure_id:
            return [e for e in self._escalations if e.failure_id == failure_id]
        return list(self._escalations)
