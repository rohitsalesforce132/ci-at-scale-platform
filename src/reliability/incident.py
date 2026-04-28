"""IncidentManager — Manage CI incidents and postmortems."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional


class IncidentSeverity(str, Enum):
    """Incident severity levels."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class IncidentStatus(str, Enum):
    """Incident status."""
    OPEN = "open"
    INVESTIGATING = "investigating"
    MITIGATED = "mitigated"
    RESOLVED = "resolved"


@dataclass
class Incident:
    """A CI incident."""
    id: str
    title: str
    severity: IncidentSeverity
    status: IncidentStatus = IncidentStatus.OPEN
    created_at: float = 0.0
    updated_at: float = 0.0
    resolved_at: Optional[float] = None
    description: str = ""
    timeline: List[str] = field(default_factory=list)
    affected_components: List[str] = field(default_factory=list)


@dataclass
class Postmortem:
    """Postmortem for a resolved incident."""
    incident_id: str
    root_cause: str
    timeline: List[str]
    action_items: List[str]
    lessons_learned: List[str]


class IncidentManager:
    """Manage CI incidents and postmortems.

    Tracks incidents from detection through resolution,
    and generates postmortem reports.
    """

    def __init__(self) -> None:
        self._incidents: Dict[str, Incident] = {}
        self._postmortems: Dict[str, Postmortem] = {}
        self._counter = 0

    def create_incident(self, title: str, severity: IncidentSeverity = IncidentSeverity.MEDIUM,
                        description: str = "") -> Incident:
        """Create a new incident.

        Args:
            title: Incident title.
            severity: Severity level.
            description: Description.

        Returns:
            Created Incident.
        """
        self._counter += 1
        incident = Incident(
            id=f"INC-{self._counter:04d}",
            title=title,
            severity=severity,
            description=description,
            created_at=time.time(),
            updated_at=time.time(),
            timeline=[f"Incident created: {title}"],
        )
        self._incidents[incident.id] = incident
        return incident

    def update_incident(self, incident_id: str, status: IncidentStatus,
                        note: str = "") -> Optional[Incident]:
        """Update incident status.

        Args:
            incident_id: Incident to update.
            status: New status.
            note: Optional note.

        Returns:
            Updated Incident or None.
        """
        incident = self._incidents.get(incident_id)
        if not incident:
            return None

        incident.status = status
        incident.updated_at = time.time()
        if note:
            incident.timeline.append(f"[{status.value}] {note}")
        if status == IncidentStatus.RESOLVED:
            incident.resolved_at = time.time()

        return incident

    def get_active_incidents(self) -> List[Incident]:
        """Get all active (non-resolved) incidents.

        Returns:
            List of active incidents.
        """
        return [i for i in self._incidents.values()
                if i.status != IncidentStatus.RESOLVED]

    def get_postmortem(self, incident_id: str) -> Optional[Postmortem]:
        """Get postmortem for a resolved incident.

        Args:
            incident_id: Incident ID.

        Returns:
            Postmortem or None.
        """
        return self._postmortems.get(incident_id)

    def create_postmortem(self, incident_id: str, root_cause: str,
                          action_items: Optional[List[str]] = None,
                          lessons: Optional[List[str]] = None) -> Optional[Postmortem]:
        """Create a postmortem for an incident.

        Args:
            incident_id: Incident to create postmortem for.
            root_cause: Root cause analysis.
            action_items: Follow-up actions.
            lessons: Lessons learned.

        Returns:
            Created Postmortem or None.
        """
        incident = self._incidents.get(incident_id)
        if not incident:
            return None

        pm = Postmortem(
            incident_id=incident_id,
            root_cause=root_cause,
            timeline=incident.timeline,
            action_items=action_items or [],
            lessons_learned=lessons or [],
        )
        self._postmortems[incident_id] = pm
        return pm

    def get_incident(self, incident_id: str) -> Optional[Incident]:
        """Get an incident by ID."""
        return self._incidents.get(incident_id)

    def get_all_incidents(self) -> List[Incident]:
        """Get all incidents."""
        return list(self._incidents.values())
