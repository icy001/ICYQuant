"""
HealthIncident — the durable record of a persistent abnormal health state.

Lifecycle:

    DETECTED → OPEN → INVESTIGATING → RECOVERING → RESOLVED
                             │
                             └── ESCALATED (failure to recover)

The incident is what later feeds alerting and incident management; it is
produced by the ComponentMonitor but owned here so the repository does not
depend on the monitor layer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Dict, Optional, Set

from .heartbeat import utcnow
from .health_status import HealthStatus


class HealthIncidentState(str, Enum):
    """Lifecycle state of a health incident."""

    DETECTED = "DETECTED"
    OPEN = "OPEN"
    INVESTIGATING = "INVESTIGATING"
    RECOVERING = "RECOVERING"
    RESOLVED = "RESOLVED"
    ESCALATED = "ESCALATED"

    @property
    def is_terminal(self) -> bool:
        return self in (HealthIncidentState.RESOLVED, HealthIncidentState.ESCALATED)


_ALLOWED_TRANSITIONS: Dict[HealthIncidentState, Set[HealthIncidentState]] = {
    HealthIncidentState.DETECTED: {
        HealthIncidentState.OPEN,
        HealthIncidentState.ESCALATED,
    },
    HealthIncidentState.OPEN: {
        HealthIncidentState.INVESTIGATING,
        HealthIncidentState.RECOVERING,
        HealthIncidentState.RESOLVED,
        HealthIncidentState.ESCALATED,
    },
    HealthIncidentState.INVESTIGATING: {
        HealthIncidentState.RECOVERING,
        HealthIncidentState.RESOLVED,
        HealthIncidentState.ESCALATED,
    },
    HealthIncidentState.RECOVERING: {
        HealthIncidentState.RESOLVED,
        HealthIncidentState.ESCALATED,
    },
    HealthIncidentState.RESOLVED: set(),
    HealthIncidentState.ESCALATED: set(),
}


class HealthIncidentTransitionError(Exception):
    """Raised when an illegal incident state transition is attempted."""


@dataclass
class HealthIncident:
    """Lifecycle record of a health problem for one component."""

    incident_id: str
    component_id: str
    severity: str
    reason: str
    state: HealthIncidentState = HealthIncidentState.DETECTED
    started_at: datetime = field(default_factory=utcnow)
    resolved_at: Optional[datetime] = None
    current_status: HealthStatus = HealthStatus.UNKNOWN

    @property
    def is_resolved(self) -> bool:
        return self.state is HealthIncidentState.RESOLVED

    def transition(
        self,
        new_state: HealthIncidentState,
        at: Optional[datetime] = None,
    ) -> "HealthIncident":
        """Move the incident to ``new_state`` (validated against the lifecycle)."""
        if new_state is self.state:
            return self
        if new_state not in _ALLOWED_TRANSITIONS[self.state]:
            raise HealthIncidentTransitionError(
                f"{self.component_id}: {self.state.value} → {new_state.value} not allowed"
            )
        self.state = new_state
        if new_state is HealthIncidentState.RESOLVED:
            self.resolved_at = at or utcnow()
        return self

    def to_dict(self) -> dict:
        return {
            "incident_id": self.incident_id,
            "component_id": self.component_id,
            "severity": self.severity,
            "reason": self.reason,
            "state": self.state.value,
            "started_at": self.started_at.isoformat(),
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "current_status": self.current_status.value,
        }


def incident_severity_for_criticality(criticality) -> str:
    """Map a component criticality to an incident severity label."""
    from ..domain.component_registry import ComponentCriticality

    if criticality is ComponentCriticality.TRADING_CRITICAL:
        return "CRITICAL"
    if criticality is ComponentCriticality.OPERATIONAL:
        return "HIGH"
    return "LOW"
