"""
IncidentCluster — a group of incidents tied together by correlation.

A cluster keeps the root incident id, its members and the worst observed
severity, so an aggregated view of a single fault family survives across
multiple incidents (spec section 37).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Union

from ..incident_severity import IncidentSeverity
from ..incident_type import IncidentType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class IncidentCluster:
    cluster_id: str
    root_incident_id: str
    incident_type: Union[IncidentType, str]
    severity: Union[IncidentSeverity, str]
    member_ids: List[str] = field(default_factory=list)
    opened_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    status: str = "OPEN"

    def __post_init__(self) -> None:
        self.incident_type = IncidentType(self.incident_type)
        self.severity = IncidentSeverity(self.severity)
        if self.root_incident_id not in self.member_ids:
            self.member_ids.insert(0, self.root_incident_id)

    # -- mutations --------------------------------------------------------

    def add_member(self, incident_id: str) -> None:
        if incident_id in self.member_ids:
            return
        self.member_ids.append(incident_id)
        self.updated_at = _utcnow()

    def escalate_severity(self, severity: Union[IncidentSeverity, str]) -> bool:
        """Raise the cluster severity; returns True if it changed."""
        severity = IncidentSeverity(severity)
        if severity <= self.severity:
            return False
        self.severity = severity
        self.updated_at = _utcnow()
        return True

    def close(self) -> None:
        self.status = "CLOSED"
        self.updated_at = _utcnow()

    def is_root(self, incident_id: str) -> bool:
        return incident_id == self.root_incident_id

    def member_count(self) -> int:
        return len(self.member_ids)

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "root_incident_id": self.root_incident_id,
            "incident_type": self.incident_type.value,
            "severity": self.severity.value,
            "member_ids": list(self.member_ids),
            "opened_at": self.opened_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "status": self.status,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IncidentCluster":
        def _parse(key: str) -> datetime:
            value = data.get(key)
            if isinstance(value, datetime):
                return value
            return datetime.fromisoformat(value)

        return cls(
            cluster_id=data["cluster_id"],
            root_incident_id=data["root_incident_id"],
            incident_type=data["incident_type"],
            severity=data["severity"],
            member_ids=list(data.get("member_ids", [])),
            opened_at=_parse("opened_at"),
            updated_at=_parse("updated_at"),
            status=data.get("status", "OPEN"),
        )

    def __repr__(self) -> str:
        return (
            f"IncidentCluster({self.cluster_id}, {self.incident_type.value}, "
            f"{self.severity.value}, members={len(self.member_ids)})"
        )
