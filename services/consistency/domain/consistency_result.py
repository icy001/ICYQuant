"""
ConsistencyResult — per-metric comparison result and aggregated check matrix.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .consistency_status import ConsistencyDomainStatus


@dataclass
class MatrixRow:
    """A single row in the consistency matrix — one metric comparison."""

    metric: str
    label: str
    expected_value: float
    actual_value: float
    delta: float
    pass_: bool  # True if expected == actual
    tolerance: float = 0.0
    details: str = ""

    @property
    def is_match(self) -> bool:
        return self.pass_

    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric": self.metric,
            "label": self.label,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "delta": self.delta,
            "pass": self.pass_,
            "tolerance": self.tolerance,
            "details": self.details,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "MatrixRow":
        return cls(
            metric=str(data["metric"]),
            label=str(data["label"]),
            expected_value=float(data["expected_value"]),
            actual_value=float(data["actual_value"]),
            delta=float(data["delta"]),
            pass_=bool(data["pass"]),
            tolerance=float(data.get("tolerance", 0)),
            details=str(data.get("details", "")),
        )


@dataclass
class CheckMatrix:
    """Aggregated check matrix across multiple metrics."""

    rows: List[MatrixRow] = field(default_factory=list)

    @property
    def all_pass(self) -> bool:
        return all(row.pass_ for row in self.rows) if self.rows else True

    @property
    def failure_count(self) -> int:
        return sum(1 for row in self.rows if not row.pass_)

    def add_row(self, row: MatrixRow) -> None:
        self.rows.append(row)

    def to_dict(self) -> Dict[str, Any]:
        return {"rows": [r.to_dict() for r in self.rows]}

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CheckMatrix":
        return cls(
            rows=[MatrixRow.from_dict(r) for r in data.get("rows", [])]
        )


def _is_within_grace_period(
    event_age_ms: int,
    grace_period_ms: int,
) -> bool:
    """Check whether an event is within the grace period window."""
    return event_age_ms < grace_period_ms


def _calculate_event_age_ms(occurred_at: Optional[datetime]) -> int:
    """Age of the event in ms: how long ago did it happen?"""
    if occurred_at is None:
        return 0
    return int(
        (datetime.now(timezone.utc) - occurred_at.replace(tzinfo=timezone.utc)
         if occurred_at.tzinfo is None else
         datetime.now(timezone.utc) - occurred_at
         ).total_seconds() * 1000
    )


def _calculate_event_lag_ms(
    occurred_at: Optional[datetime],
    updated_at: Optional[datetime],
) -> int:
    """Calculate the lag in ms between execution occurred and domain last-update."""
    if occurred_at is None or updated_at is None:
        return 0
    a = occurred_at.replace(tzinfo=timezone.utc) if occurred_at.tzinfo is None else occurred_at
    b = updated_at.replace(tzinfo=timezone.utc) if updated_at.tzinfo is None else updated_at
    delta = b - a
    return int(delta.total_seconds() * 1000)


@dataclass
class ConsistencyResult:
    """Result for a single consistency check across one domain pair."""

    domain: str  # "POSITION" | "LEDGER"
    status: ConsistencyDomainStatus = ConsistencyDomainStatus.CONSISTENT
    matrix: CheckMatrix = field(default_factory=CheckMatrix)

    # Lag tracking
    event_lag_ms: int = 0
    grace_period_ms: int = 5000

    # Failure details
    failure_type: str = ""
    expected_value: float = 0.0
    actual_value: float = 0.0
    delta: float = 0.0

    source_execution_id: str = ""
    detected_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def with_grace_evaluation(
        self,
        event_occurred_at: Optional[datetime] = None,
        domain_updated_at: Optional[datetime] = None,
    ) -> "ConsistencyResult":
        """Evaluate whether a detected mismatch might just be async lag.

        - event_lag_ms: monitors the propagation delay (domain update - event)
        - grace decision: if the event is recent (< grace_period) → DEGRADED
          otherwise the mismatch is real → INCONSISTENT
        """
        if self.status != ConsistencyDomainStatus.CONSISTENT:
            # Track propagation lag for monitoring
            self.event_lag_ms = _calculate_event_lag_ms(
                event_occurred_at, domain_updated_at
            )
            # Grace period: use event age (how long ago did it happen?)
            event_age_ms = _calculate_event_age_ms(event_occurred_at)
            if _is_within_grace_period(event_age_ms, self.grace_period_ms):
                self.status = ConsistencyDomainStatus.DEGRADED
        return self

    @property
    def is_consistent(self) -> bool:
        return self.status == ConsistencyDomainStatus.CONSISTENT

    @property
    def is_degraded(self) -> bool:
        return self.status == ConsistencyDomainStatus.DEGRADED

    @property
    def is_inconsistent(self) -> bool:
        return self.status == ConsistencyDomainStatus.INCONSISTENT

    def to_dict(self) -> Dict[str, Any]:
        return {
            "domain": self.domain,
            "status": self.status.value,
            "matrix": self.matrix.to_dict(),
            "event_lag_ms": self.event_lag_ms,
            "grace_period_ms": self.grace_period_ms,
            "failure_type": self.failure_type,
            "expected_value": self.expected_value,
            "actual_value": self.actual_value,
            "delta": self.delta,
            "source_execution_id": self.source_execution_id,
            "detected_at": self.detected_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "ConsistencyResult":
        detected = data.get("detected_at")
        return cls(
            domain=str(data["domain"]),
            status=ConsistencyDomainStatus(data.get("status", "CONSISTENT")),
            matrix=CheckMatrix.from_dict(data.get("matrix", {})),
            event_lag_ms=int(data.get("event_lag_ms", 0)),
            grace_period_ms=int(data.get("grace_period_ms", 5000)),
            failure_type=str(data.get("failure_type", "")),
            expected_value=float(data.get("expected_value", 0)),
            actual_value=float(data.get("actual_value", 0)),
            delta=float(data.get("delta", 0)),
            source_execution_id=str(data.get("source_execution_id", "")),
            detected_at=datetime.fromisoformat(detected)
            if detected
            else datetime.now(timezone.utc),
        )
