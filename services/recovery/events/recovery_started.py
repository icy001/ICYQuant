from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional


@dataclass
class RecoveryStarted:
    """Emitted when a recovery job begins execution."""

    EVENT_TYPE = "RECOVERY_STARTED"

    job_id: str
    recovery_type: str
    recovery_key: str
    source_check_id: str
    account_id: Optional[str] = None
    instrument_id: Optional[str] = None
    execution_id: Optional[str] = None
    order_id: Optional[str] = None
    attempt: int = 1
    event_type: str = EVENT_TYPE
    event_id: str = ""
    correlation_id: str = ""
    causation_id: str = ""
    lineage_id: str = ""
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "job_id": self.job_id,
            "recovery_type": self.recovery_type,
            "recovery_key": self.recovery_key,
            "source_check_id": self.source_check_id,
            "account_id": self.account_id,
            "instrument_id": self.instrument_id,
            "execution_id": self.execution_id,
            "order_id": self.order_id,
            "attempt": self.attempt,
            "event_type": self.event_type,
            "event_id": self.event_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "lineage_id": self.lineage_id,
            "started_at": self.started_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecoveryStarted":
        return cls(
            job_id=data["job_id"],
            recovery_type=data["recovery_type"],
            recovery_key=data["recovery_key"],
            source_check_id=data["source_check_id"],
            account_id=data.get("account_id"),
            instrument_id=data.get("instrument_id"),
            execution_id=data.get("execution_id"),
            order_id=data.get("order_id"),
            attempt=data.get("attempt", 1),
            event_type=data.get("event_type", cls.EVENT_TYPE),
            event_id=data.get("event_id", ""),
            correlation_id=data.get("correlation_id", ""),
            causation_id=data.get("causation_id", ""),
            lineage_id=data.get("lineage_id", ""),
            started_at=datetime.fromisoformat(data["started_at"])
            if "started_at" in data
            else datetime.now(timezone.utc),
        )

    @classmethod
    def from_job(cls, job: "RecoveryJob") -> "RecoveryStarted":  # noqa: F821
        return cls(
            job_id=job.job_id,
            recovery_type=job.recovery_type.value,
            recovery_key=job.recovery_key,
            source_check_id=job.source_check_id,
            account_id=job.account_id,
            instrument_id=job.instrument_id,
            execution_id=job.execution_id,
            order_id=job.order_id,
            attempt=job.attempt,
            correlation_id=job.correlation_id,
            causation_id=job.causation_id,
            lineage_id=job.lineage_id,
        )
