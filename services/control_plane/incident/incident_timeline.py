"""
IncidentTimeline — the ordered, immutable audit trail of an incident.

Every detection, policy trigger, restriction, recovery step and resolution is
appended so the full story is reconstructable for review / postmortem / audit
(spec section 12).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class IncidentTimelineEntry:
    occurred_at: datetime
    event_type: str
    detail: str = ""
    actor: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "occurred_at": self.occurred_at.isoformat(),
            "event_type": self.event_type,
            "detail": self.detail,
            "actor": self.actor,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IncidentTimelineEntry":
        return cls(
            occurred_at=datetime.fromisoformat(data["occurred_at"]),
            event_type=data["event_type"],
            detail=data.get("detail", ""),
            actor=data.get("actor", ""),
        )


@dataclass
class IncidentTimeline:
    """Ordered list of timeline entries for a single incident."""

    entries: List[IncidentTimelineEntry] = field(default_factory=list)

    def add(
        self,
        event_type: str,
        detail: str = "",
        actor: str = "",
        occurred_at: datetime | None = None,
    ) -> IncidentTimelineEntry:
        entry = IncidentTimelineEntry(
            occurred_at=occurred_at or _utcnow(),
            event_type=event_type,
            detail=detail,
            actor=actor,
        )
        self.entries.append(entry)
        return entry

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)

    def to_dict(self) -> Dict[str, Any]:
        return {"entries": [e.to_dict() for e in self.entries]}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "IncidentTimeline":
        return cls(
            entries=[IncidentTimelineEntry.from_dict(e) for e in data.get("entries", [])]
        )
