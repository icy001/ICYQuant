"""
DetectionResult — the outcome of evaluating detection rules against an event.

A detection is NOT an incident yet: it only says "this event is anomalous".
The Correlation Engine decides whether it becomes a new incident, an update,
a child or a duplicate (spec section 5, 16).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..incident_scope import IncidentScope
from ..incident_severity import IncidentSeverity
from ..incident_source import IncidentSource
from ..incident_type import IncidentType


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class DetectionResult:
    matched: bool
    rule_id: str = ""
    event_id: str = ""
    event_type: str = ""
    incident_type: Optional[IncidentType] = None
    severity: Optional[IncidentSeverity] = None
    scope: Optional[IncidentScope] = None
    source: Optional[IncidentSource] = None
    service: str = ""
    account: str = ""
    strategy: str = ""
    instrument: str = ""
    venue: str = ""
    detail: str = ""
    occurred_at: Optional[datetime] = None
    suppressed: bool = False
    suppression_reason: str = ""

    def __post_init__(self) -> None:
        if self.occurred_at is None:
            self.occurred_at = _utcnow()
        if self.incident_type is not None and not isinstance(self.incident_type, IncidentType):
            self.incident_type = IncidentType(self.incident_type)
        if self.severity is not None and not isinstance(self.severity, IncidentSeverity):
            self.severity = IncidentSeverity(self.severity)
        if self.scope is not None and not isinstance(self.scope, IncidentScope):
            self.scope = IncidentScope(self.scope)
        if self.source is not None and not isinstance(self.source, IncidentSource):
            self.source = IncidentSource(self.source)

    @classmethod
    def unmatched(cls, event_type: str = "") -> "DetectionResult":
        return cls(matched=False, event_type=event_type)

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "matched": self.matched,
            "rule_id": self.rule_id,
            "event_id": self.event_id,
            "event_type": self.event_type,
            "incident_type": self.incident_type.value if self.incident_type else None,
            "severity": self.severity.value if self.severity else None,
            "scope": self.scope.value if self.scope else None,
            "source": self.source.value if self.source else None,
            "service": self.service,
            "account": self.account,
            "strategy": self.strategy,
            "instrument": self.instrument,
            "venue": self.venue,
            "detail": self.detail,
            "occurred_at": self.occurred_at.isoformat(),
            "suppressed": self.suppressed,
            "suppression_reason": self.suppression_reason,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DetectionResult":
        occurred_at = data.get("occurred_at")
        return cls(
            matched=data["matched"],
            rule_id=data.get("rule_id", ""),
            event_id=data.get("event_id", ""),
            event_type=data.get("event_type", ""),
            incident_type=data.get("incident_type"),
            severity=data.get("severity"),
            scope=data.get("scope"),
            source=data.get("source"),
            service=data.get("service", ""),
            account=data.get("account", ""),
            strategy=data.get("strategy", ""),
            instrument=data.get("instrument", ""),
            venue=data.get("venue", ""),
            detail=data.get("detail", ""),
            occurred_at=datetime.fromisoformat(occurred_at) if occurred_at else None,
            suppressed=data.get("suppressed", False),
            suppression_reason=data.get("suppression_reason", ""),
        )

    def __repr__(self) -> str:
        if not self.matched:
            return "DetectionResult(unmatched)"
        return (
            f"DetectionResult({self.rule_id}, {self.incident_type.value}, "
            f"{self.severity.value}, suppressed={self.suppressed})"
        )
