"""
RecoveryStepStarted — a single recovery step began.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RecoveryStepStarted:
    event_type = "RECOVERY_STEP_STARTED"

    def __init__(
        self,
        recovery_id: str,
        step_id: str,
        step_type: str = "",
        attempt: int = 1,
        correlation_id: str = "",
        started_at: datetime | None = None,
    ) -> None:
        self.recovery_id = recovery_id
        self.step_id = step_id
        self.step_type = step_type
        self.attempt = attempt
        self.correlation_id = correlation_id
        self.started_at = started_at or _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "recovery_id": self.recovery_id,
            "step_id": self.step_id,
            "step_type": self.step_type,
            "attempt": self.attempt,
            "correlation_id": self.correlation_id,
            "started_at": self.started_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryStepStarted":
        started = data.get("started_at")
        return cls(
            recovery_id=data["recovery_id"],
            step_id=data["step_id"],
            step_type=data.get("step_type", ""),
            attempt=data.get("attempt", 1),
            correlation_id=data.get("correlation_id", ""),
            started_at=datetime.fromisoformat(started) if started else None,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RecoveryStepStarted):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"RecoveryStepStarted(step_id={self.step_id!r})"
