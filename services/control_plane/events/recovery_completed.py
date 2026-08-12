"""
RecoveryCompleted — a recovery finished successfully.

Trading is *not* automatically reopened by this event; the trading gate only
reopens after a subsequent policy evaluation agrees.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RecoveryCompleted:
    event_type = "RECOVERY_COMPLETED"

    def __init__(
        self,
        recovery_id: str,
        ramp_up_level: str = "LEVEL_1",
        correlation_id: str = "",
        completed_at: datetime | None = None,
    ) -> None:
        self.recovery_id = recovery_id
        self.ramp_up_level = ramp_up_level
        self.correlation_id = correlation_id
        self.completed_at = completed_at or _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "recovery_id": self.recovery_id,
            "ramp_up_level": self.ramp_up_level,
            "correlation_id": self.correlation_id,
            "completed_at": self.completed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryCompleted":
        completed = data.get("completed_at")
        return cls(
            recovery_id=data["recovery_id"],
            ramp_up_level=data.get("ramp_up_level", "LEVEL_1"),
            correlation_id=data.get("correlation_id", ""),
            completed_at=datetime.fromisoformat(completed) if completed else None,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RecoveryCompleted):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"RecoveryCompleted(recovery_id={self.recovery_id!r})"
