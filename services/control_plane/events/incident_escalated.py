"""
IncidentEscalated — an incident moved to ESCALATED (recovery failed) or its
severity was raised.

Example:

    incident_id: INC-20260812-000042
    severity: CRITICAL
    detail: recovery REC-0017 failed
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from ..incident.incident_severity import IncidentSeverity


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IncidentEscalated:
    event_type = "INCIDENT_ESCALATED"

    def __init__(
        self,
        incident_id: str,
        severity: Union[IncidentSeverity, str],
        detail: str = "",
        actor: str = "",
        correlation_id: str = "",
        escalated_at: Optional[datetime] = None,
    ) -> None:
        self.incident_id = incident_id
        self.severity = IncidentSeverity(severity)
        self.detail = detail
        self.actor = actor
        self.correlation_id = correlation_id
        self.escalated_at = escalated_at or _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "incident_id": self.incident_id,
            "severity": self.severity.value,
            "detail": self.detail,
            "actor": self.actor,
            "correlation_id": self.correlation_id,
            "escalated_at": self.escalated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IncidentEscalated":
        escalated_at = data.get("escalated_at")
        return cls(
            incident_id=data["incident_id"],
            severity=data["severity"],
            detail=data.get("detail", ""),
            actor=data.get("actor", ""),
            correlation_id=data.get("correlation_id", ""),
            escalated_at=datetime.fromisoformat(escalated_at) if escalated_at else None,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IncidentEscalated):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"IncidentEscalated({self.incident_id}, {self.severity.value})"
