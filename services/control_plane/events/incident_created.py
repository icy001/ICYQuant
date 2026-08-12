"""
IncidentCreated — a new incident was created from a detection.

Example:

    incident_id: INC-20260812-000001
    type: POSITION_INTEGRITY_FAILURE
    severity: CRITICAL
    scope: GLOBAL
    source: RECONCILIATION
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from ..incident.incident_scope import IncidentScope
from ..incident.incident_severity import IncidentSeverity
from ..incident.incident_source import IncidentSource
from ..incident.incident_type import IncidentType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class IncidentCreated:
    event_type = "INCIDENT_CREATED"

    def __init__(
        self,
        incident_id: str,
        type: Union[IncidentType, str],
        severity: Union[IncidentSeverity, str],
        scope: Union[IncidentScope, str],
        source: Union[IncidentSource, str],
        fingerprint: str = "",
        correlation_id: str = "",
        created_at: Optional[datetime] = None,
    ) -> None:
        self.incident_id = incident_id
        self.type = IncidentType(type)
        self.severity = IncidentSeverity(severity)
        self.scope = IncidentScope(scope)
        self.source = IncidentSource(source)
        self.fingerprint = fingerprint
        self.correlation_id = correlation_id
        self.created_at = created_at or _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "incident_id": self.incident_id,
            "type": self.type.value,
            "severity": self.severity.value,
            "scope": self.scope.value,
            "source": self.source.value,
            "fingerprint": self.fingerprint,
            "correlation_id": self.correlation_id,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IncidentCreated":
        created_at = data.get("created_at")
        return cls(
            incident_id=data["incident_id"],
            type=data["type"],
            severity=data["severity"],
            scope=data["scope"],
            source=data["source"],
            fingerprint=data.get("fingerprint", ""),
            correlation_id=data.get("correlation_id", ""),
            created_at=datetime.fromisoformat(created_at) if created_at else None,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, IncidentCreated):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"IncidentCreated({self.incident_id}, {self.type.value})"
