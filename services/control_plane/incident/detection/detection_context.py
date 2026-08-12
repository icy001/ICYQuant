"""
DetectionContext — normalized view of a raw system event.

The Detection Engine normalizes arbitrary events (health, risk, execution,
position, ledger, reconciliation, recovery) into one shape before rules are
evaluated (spec section 3).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class DetectionContext:
    event_id: str = ""
    event_type: str = ""
    occurred_at: Optional[datetime] = None
    service: str = ""
    account: str = ""
    strategy: str = ""
    instrument: str = ""
    venue: str = ""
    detail: str = ""
    raw: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.occurred_at is None:
            self.occurred_at = _utcnow()

    @classmethod
    def from_event(cls, event: Dict[str, Any]) -> "DetectionContext":
        occurred_at = event.get("occurred_at")
        if isinstance(occurred_at, str):
            occurred_at = datetime.fromisoformat(occurred_at)
        return cls(
            event_id=str(event.get("event_id", "")),
            event_type=str(event.get("event_type", "")),
            occurred_at=occurred_at,
            service=str(event.get("service", "")),
            account=str(event.get("account", "")),
            strategy=str(event.get("strategy", "")),
            instrument=str(event.get("instrument", "")),
            venue=str(event.get("venue", "")),
            detail=str(event.get("detail", "")),
            raw=dict(event),
        )

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "occurred_at": self.occurred_at.isoformat(),
            "service": self.service,
            "account": self.account,
            "strategy": self.strategy,
            "instrument": self.instrument,
            "venue": self.venue,
            "detail": self.detail,
            "raw": dict(self.raw),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "DetectionContext":
        occurred_at = data.get("occurred_at")
        return cls(
            event_id=data.get("event_id", ""),
            event_type=data.get("event_type", ""),
            occurred_at=datetime.fromisoformat(occurred_at) if occurred_at else None,
            service=data.get("service", ""),
            account=data.get("account", ""),
            strategy=data.get("strategy", ""),
            instrument=data.get("instrument", ""),
            venue=data.get("venue", ""),
            detail=data.get("detail", ""),
            raw=dict(data.get("raw", {})),
        )
