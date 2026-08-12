"""
RecoveryFailed — a recovery step failed.

Carries the failure classification (TRANSIENT / RECOVERABLE / INTEGRITY /
FATAL), whether the failure will be auto-retried, and whether the recovery has
been escalated.  Trading stays halted — recovery never auto-reopens trading.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class RecoveryFailed:
    event_type = "RECOVERY_FAILED"

    def __init__(
        self,
        recovery_id: str,
        step_id: str = "",
        error: str = "",
        failure_class: str = "",
        retryable: bool = False,
        escalated: bool = False,
        correlation_id: str = "",
        failed_at: datetime | None = None,
    ) -> None:
        self.recovery_id = recovery_id
        self.step_id = step_id
        self.error = error
        self.failure_class = failure_class
        self.retryable = retryable
        self.escalated = escalated
        self.correlation_id = correlation_id
        self.failed_at = failed_at or _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "recovery_id": self.recovery_id,
            "step_id": self.step_id,
            "error": self.error,
            "failure_class": self.failure_class,
            "retryable": self.retryable,
            "escalated": self.escalated,
            "correlation_id": self.correlation_id,
            "failed_at": self.failed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryFailed":
        failed = data.get("failed_at")
        return cls(
            recovery_id=data["recovery_id"],
            step_id=data.get("step_id", ""),
            error=data.get("error", ""),
            failure_class=data.get("failure_class", ""),
            retryable=data.get("retryable", False),
            escalated=data.get("escalated", False),
            correlation_id=data.get("correlation_id", ""),
            failed_at=datetime.fromisoformat(failed) if failed else None,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, RecoveryFailed):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"RecoveryFailed(step_id={self.step_id!r}, error={self.error!r})"
