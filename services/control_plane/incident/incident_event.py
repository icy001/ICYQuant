"""
IncidentEvent — a single recorded event in an incident's lifecycle.

Every state change produces an IncidentEvent (spec section 13).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IncidentEventType(str, Enum):
    INCIDENT_CREATED = "INCIDENT_CREATED"
    INCIDENT_UPDATED = "INCIDENT_UPDATED"
    INCIDENT_ESCALATED = "INCIDENT_ESCALATED"
    INCIDENT_ACKNOWLEDGED = "INCIDENT_ACKNOWLEDGED"
    INCIDENT_MITIGATION_STARTED = "INCIDENT_MITIGATION_STARTED"
    INCIDENT_RESOLVED = "INCIDENT_RESOLVED"
    INCIDENT_REOPENED = "INCIDENT_REOPENED"


@dataclass
class IncidentEvent:
    event_type: IncidentEventType
    incident_id: str
    occurred_at: datetime
    actor: str = ""
    detail: str = ""
    correlation_id: str = ""

    def __post_init__(self) -> None:
        if not isinstance(self.event_type, IncidentEventType):
            self.event_type = IncidentEventType(self.event_type)
        if self.occurred_at is None:
            self.occurred_at = _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "incident_id": self.incident_id,
            "occurred_at": self.occurred_at.isoformat(),
            "actor": self.actor,
            "detail": self.detail,
            "correlation_id": self.correlation_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IncidentEvent":
        occurred_at = data.get("occurred_at")
        return cls(
            event_type=IncidentEventType(data["event_type"]),
            incident_id=data["incident_id"],
            occurred_at=datetime.fromisoformat(occurred_at) if occurred_at else _utcnow(),
            actor=data.get("actor", ""),
            detail=data.get("detail", ""),
            correlation_id=data.get("correlation_id", ""),
        )
