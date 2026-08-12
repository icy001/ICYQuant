"""
RecoveryStepCompleted — a recovery step finished successfully.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RecoveryStepCompleted:
    event_type = "RECOVERY_STEP_COMPLETED"

    def __init__(
        self,
        recovery_id: str,
        step_id: str,
        step_type: str = "",
        attempt: int = 1,
        output: Dict[str, Any] | None = None,
        correlation_id: str = "",
        completed_at: datetime | None = None,
    ) -> None:
        self.recovery_id = recovery_id
        self.step_id = step_id
        self.step_type = step_type
        self.attempt = attempt
        self.output = dict(output or {})
        self.correlation_id = correlation_id
        self.completed_at = completed_at or _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "recovery_id": self.recovery_id,
            "step_id": self.step_id,
            "step_type": self.step_type,
            "attempt": self.attempt,
            "output": dict(self.output),
            "correlation_id": self.correlation_id,
            "completed_at": self.completed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryStepCompleted":
        completed = data.get("completed_at")
        return cls(
            recovery_id=data["recovery_id"],
            step_id=data["step_id"],
            step_type=data.get("step_type", ""),
            attempt=data.get("attempt", 1),
            output=dict(data.get("output", {})),
            correlation_id=data.get("correlation_id", ""),
            completed_at=datetime.fromisoformat(completed) if completed else None,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RecoveryStepCompleted):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"RecoveryStepCompleted(step_id={self.step_id!r})"
