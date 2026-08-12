"""
IncidentResolved — an incident was closed with a resolution reason.

Never a bare status flip: the event always carries the resolution reason, the
actor who resolved it and the verification result (spec section 29).
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IncidentResolved:
    event_type = "INCIDENT_RESOLVED"

    def __init__(
        self,
        incident_id: str,
        resolution_reason: str,
        resolved_by: str,
        verification_result: str = "VERIFIED",
        correlation_id: str = "",
        resolved_at: Optional[datetime] = None,
    ) -> None:
        self.incident_id = incident_id
        self.resolution_reason = resolution_reason
        self.resolved_by = resolved_by
        self.verification_result = verification_result
        self.correlation_id = correlation_id
        self.resolved_at = resolved_at or _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "incident_id": self.incident_id,
            "resolution_reason": self.resolution_reason,
            "resolved_by": self.resolved_by,
            "verification_result": self.verification_result,
            "correlation_id": self.correlation_id,
            "resolved_at": self.resolved_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IncidentResolved":
        resolved_at = data.get("resolved_at")
        return cls(
            incident_id=data["incident_id"],
            resolution_reason=data["resolution_reason"],
            resolved_by=data["resolved_by"],
            verification_result=data.get("verification_result", "VERIFIED"),
            correlation_id=data.get("correlation_id", ""),
            resolved_at=datetime.fromisoformat(resolved_at) if resolved_at else None,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IncidentResolved):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"IncidentResolved({self.incident_id}, {self.resolution_reason})"
