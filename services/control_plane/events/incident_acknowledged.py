"""
IncidentAcknowledged — a human acknowledged the incident.

Acknowledging is NOT resolving: the operator may know about the problem
without the problem being fixed (spec section 31).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IncidentAcknowledged:
    event_type = "INCIDENT_ACKNOWLEDGED"

    def __init__(
        self,
        incident_id: str,
        actor: str = "",
        detail: str = "",
        correlation_id: str = "",
        acknowledged_at: Optional[datetime] = None,
    ) -> None:
        self.incident_id = incident_id
        self.actor = actor
        self.detail = detail
        self.correlation_id = correlation_id
        self.acknowledged_at = acknowledged_at or _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "incident_id": self.incident_id,
            "actor": self.actor,
            "detail": self.detail,
            "correlation_id": self.correlation_id,
            "acknowledged_at": self.acknowledged_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IncidentAcknowledged":
        acknowledged_at = data.get("acknowledged_at")
        return cls(
            incident_id=data["incident_id"],
            actor=data.get("actor", ""),
            detail=data.get("detail", ""),
            correlation_id=data.get("correlation_id", ""),
            acknowledged_at=datetime.fromisoformat(acknowledged_at)
            if acknowledged_at
            else None,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IncidentAcknowledged):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"IncidentAcknowledged({self.incident_id})"
