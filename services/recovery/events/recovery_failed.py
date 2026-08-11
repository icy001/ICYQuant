from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class RecoveryFailed:
    """Emitted when a recovery job fails (including escalation)."""

    EVENT_TYPE = "RECOVERY_FAILED"

    job_id: str
    recovery_type: str
    recovery_key: str
    source_check_id: str
    failure_code: str
    failure_reason: str
    attempt: int = 1
    max_attempts: int = 3
    escalated: bool = False
    event_type: str = EVENT_TYPE
    event_id: str = ""
    correlation_id: str = ""
    causation_id: str = ""
    lineage_id: str = ""
    account_id: Optional[str] = None
    instrument_id: Optional[str] = None
    failed_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "recovery_type": self.recovery_type,
            "recovery_key": self.recovery_key,
            "source_check_id": self.source_check_id,
            "failure_code": self.failure_code,
            "failure_reason": self.failure_reason,
            "attempt": self.attempt,
            "max_attempts": self.max_attempts,
            "escalated": self.escalated,
            "event_type": self.event_type,
            "event_id": self.event_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "lineage_id": self.lineage_id,
            "account_id": self.account_id,
            "instrument_id": self.instrument_id,
            "failed_at": self.failed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryFailed":
        return cls(
            job_id=data["job_id"],
            recovery_type=data["recovery_type"],
            recovery_key=data["recovery_key"],
            source_check_id=data["source_check_id"],
            failure_code=data["failure_code"],
            failure_reason=data["failure_reason"],
            attempt=data.get("attempt", 1),
            max_attempts=data.get("max_attempts", 3),
            escalated=data.get("escalated", False),
            event_type=data.get("event_type", cls.EVENT_TYPE),
            event_id=data.get("event_id", ""),
            correlation_id=data.get("correlation_id", ""),
            causation_id=data.get("causation_id", ""),
            lineage_id=data.get("lineage_id", ""),
            account_id=data.get("account_id"),
            instrument_id=data.get("instrument_id"),
            failed_at=datetime.fromisoformat(data["failed_at"])
            if "failed_at" in data
            else datetime.now(timezone.utc),
        )

    @classmethod
    def from_job(cls, job: "RecoveryJob") -> "RecoveryFailed":  # noqa: F821
        return cls(
            job_id=job.job_id,
            recovery_type=job.recovery_type.value,
            recovery_key=job.recovery_key,
            source_check_id=job.source_check_id,
            failure_code=job.failure_code or "UNKNOWN",
            failure_reason=job.failure_reason or "No reason provided",
            attempt=job.attempt,
            max_attempts=job.max_attempts,
            escalated=job.status.value == "ESCALATED",
            correlation_id=job.correlation_id,
            causation_id=job.causation_id,
            lineage_id=job.lineage_id,
            account_id=job.account_id,
            instrument_id=job.instrument_id,
        )
