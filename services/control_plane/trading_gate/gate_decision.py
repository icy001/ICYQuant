"""
GateDecision — the strict ALLOW / DENY result plus its auditable record.

A :class:`GateDecisionRecord` is the *decision snapshot*: it captures not only
the outcome but also the exact inputs that produced it (system state, health,
kill switch state, market data freshness, policy version, correlation id).
This makes every past decision reproducible for audit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict

from .gate_reason import GateReason


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class GateDecision(str, Enum):
    """Strict decision — the gate never returns a fuzzy state."""

    ALLOW = "ALLOW"
    DENY = "DENY"


class GateSeverity(str, Enum):
    """Severity of a gate decision (for alerting / prioritisation)."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class GateDecisionRecord:
    """Auditable snapshot of one gate evaluation."""

    decision: GateDecision
    reason: GateReason
    severity: GateSeverity = GateSeverity.INFO
    evaluated_at: datetime = field(default_factory=_utcnow)
    policy_version: str = ""
    correlation_id: str = ""
    order_id: str = ""
    snapshot: Dict[str, Any] = field(default_factory=dict)

    # -- convenience -----------------------------------------------------

    @property
    def is_allow(self) -> bool:
        return self.decision is GateDecision.ALLOW

    @property
    def is_deny(self) -> bool:
        return self.decision is GateDecision.DENY

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reason": self.reason.value,
            "severity": self.severity.value,
            "evaluated_at": self.evaluated_at.isoformat(),
            "policy_version": self.policy_version,
            "correlation_id": self.correlation_id,
            "order_id": self.order_id,
            "snapshot": dict(self.snapshot),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "GateDecisionRecord":
        return cls(
            decision=GateDecision(data["decision"]),
            reason=GateReason(data["reason"]),
            severity=GateSeverity(data.get("severity", "INFO")),
            evaluated_at=datetime.fromisoformat(data["evaluated_at"]),
            policy_version=data.get("policy_version", ""),
            correlation_id=data.get("correlation_id", ""),
            order_id=data.get("order_id", ""),
            snapshot=dict(data.get("snapshot", {})),
        )
