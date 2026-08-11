"""
CONSISTENCY_RESTORED event.

Emitted after a previously inconsistent state has been repaired and
the re-check passes.  Carries the original check_id so that the
lifecycle can be traced end-to-end.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class ConsistencyRestored:
    """Emitted when consistency is restored after repair."""

    check_id: str
    account_id: str
    instrument_id: str
    domain: str  # "POSITION" | "LEDGER" | "CROSS"

    previous_failure_type: str = ""
    previous_delta: float = 0.0
    repair_duration_ms: int = 0

    event_type: str = "CONSISTENCY_RESTORED"
    event_id: str = ""
    correlation_id: str = ""
    causation_id: str = ""
    lineage_id: str = ""

    restored_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "check_id": self.check_id,
            "account_id": self.account_id,
            "instrument_id": self.instrument_id,
            "domain": self.domain,
            "previous_failure_type": self.previous_failure_type,
            "previous_delta": self.previous_delta,
            "repair_duration_ms": self.repair_duration_ms,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "lineage_id": self.lineage_id,
            "restored_at": self.restored_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConsistencyRestored":
        restored = data.get("restored_at")
        return cls(
            check_id=str(data["check_id"]),
            account_id=str(data["account_id"]),
            instrument_id=str(data["instrument_id"]),
            domain=str(data["domain"]),
            previous_failure_type=str(data.get("previous_failure_type", "")),
            previous_delta=float(data.get("previous_delta", 0)),
            repair_duration_ms=int(data.get("repair_duration_ms", 0)),
            event_type=str(data.get("event_type", "CONSISTENCY_RESTORED")),
            event_id=str(data.get("event_id", "")),
            correlation_id=str(data.get("correlation_id", "")),
            causation_id=str(data.get("causation_id", "")),
            lineage_id=str(data.get("lineage_id", "")),
            restored_at=datetime.fromisoformat(restored)
            if restored
            else datetime.now(timezone.utc),
        )
