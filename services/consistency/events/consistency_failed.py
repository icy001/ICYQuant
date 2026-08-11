"""
CONSISTENCY_CHECK_FAILED event.

Emitted when a consistency check finds any mismatch that exceeds the
grace period.  The event carries full diagnostics so that downstream
systems (alerting, reconciliation engine) can act directly.

This event does NOT implement heal-by-emit semantics — it is a pure
observation event.  Reconciliation is triggered separately.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


@dataclass
class ConsistencyFailed:
    """Emitted on consistency check failure."""

    check_id: str
    account_id: str
    instrument_id: str
    domain: str  # "POSITION" | "LEDGER" | "CROSS"
    failure_type: str
    expected_value: float
    actual_value: float
    delta: float
    source_execution_id: str = ""

    event_type: str = "CONSISTENCY_CHECK_FAILED"
    event_id: str = ""
    correlation_id: str = ""
    causation_id: str = ""
    lineage_id: str = ""

    severity: str = "WARNING"  # WARNING | CRITICAL
    grace_period_exceeded: bool = True
    detail: str = ""

    detected_at: datetime = field(
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
            "failure_type": self.failure_type,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "delta": self.delta,
            "source_execution_id": self.source_execution_id,
            "correlation_id": self.correlation_id,
            "causation_id": self.causation_id,
            "lineage_id": self.lineage_id,
            "severity": self.severity,
            "grace_period_exceeded": self.grace_period_exceeded,
            "detail": self.detail,
            "detected_at": self.detected_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConsistencyFailed":
        detected = data.get("detected_at")
        return cls(
            check_id=str(data["check_id"]),
            account_id=str(data["account_id"]),
            instrument_id=str(data["instrument_id"]),
            domain=str(data["domain"]),
            failure_type=str(data["failure_type"]),
            expected_value=float(data["expected_value"]),
            actual_value=float(data["actual_value"]),
            delta=float(data["delta"]),
            source_execution_id=str(data.get("source_execution_id", "")),
            event_type=str(data.get("event_type", "CONSISTENCY_CHECK_FAILED")),
            event_id=str(data.get("event_id", "")),
            correlation_id=str(data.get("correlation_id", "")),
            causation_id=str(data.get("causation_id", "")),
            lineage_id=str(data.get("lineage_id", "")),
            severity=str(data.get("severity", "WARNING")),
            grace_period_exceeded=bool(data.get("grace_period_exceeded", True)),
            detail=str(data.get("detail", "")),
            detected_at=datetime.fromisoformat(detected)
            if detected
            else datetime.now(timezone.utc),
        )
