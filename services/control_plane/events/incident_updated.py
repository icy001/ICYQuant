"""
IncidentUpdated — an existing incident's context or metadata changed.

Carries the same incident identity so subscribers can merge updates into the
open incident instead of creating a new one.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IncidentUpdated:
    event_type = "INCIDENT_UPDATED"

    def __init__(
        self,
        incident_id: str,
        severity: str = "",
        status: str = "",
        detail: str = "",
        correlation_id: str = "",
        updated_at: Optional[datetime] = None,
    ) -> None:
        self.incident_id = incident_id
        self.severity = severity
        self.status = status
        self.detail = detail
        self.correlation_id = correlation_id
        self.updated_at = updated_at or _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "incident_id": self.incident_id,
            "severity": self.severity,
            "status": self.status,
            "detail": self.detail,
            "correlation_id": self.correlation_id,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IncidentUpdated":
        updated_at = data.get("updated_at")
        return cls(
            incident_id=data["incident_id"],
            severity=data.get("severity", ""),
            status=data.get("status", ""),
            detail=data.get("detail", ""),
            correlation_id=data.get("correlation_id", ""),
            updated_at=datetime.fromisoformat(updated_at) if updated_at else None,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IncidentUpdated):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"IncidentUpdated({self.incident_id})"
