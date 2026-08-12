"""
StateDecision — the actionable output of a Control Plane evaluation.

Evaluation pipeline (event-driven, NOT a direct DB write):

    evaluate()
        │
        ▼
    StateDecision  (decision / reason / severity / source)
        │
        ▼
    SYSTEM_STATE_CHANGED / TRADING_STATE_CHANGED
        │
        ▼
    Projection (ControlPlaneSnapshot)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from .system_state import StateReasonCode
from .trading_gate import GateDecision, Severity, TradingGateResult


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class StateDecision:
    """A single, auditable state decision produced by evaluation."""

    decision: str
    """e.g. TRADING_ALLOW / TRADING_DENY / TRADING_REVIEW"""

    reason: StateReasonCode
    """Mandatory — every decision must carry a reason code."""

    severity: Severity
    source: str = "control-plane"
    detail: str = ""
    decided_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if self.decided_at is None:
            self.decided_at = _utcnow()

    # -- factories --------------------------------------------------------

    @classmethod
    def from_gate(cls, gate_result: TradingGateResult) -> "StateDecision":
        if gate_result.decision is GateDecision.ALLOW:
            decision = "TRADING_ALLOW"
        else:
            decision = "TRADING_DENY"
        return cls(
            decision=decision,
            reason=gate_result.reason,
            severity=gate_result.severity,
            source=gate_result.source,
        )

    @classmethod
    def from_values(
        cls,
        decision: str,
        reason: StateReasonCode,
        severity: Severity,
        source: str = "control-plane",
        detail: str = "",
    ) -> "StateDecision":
        return cls(
            decision=decision,
            reason=reason,
            severity=severity,
            source=source,
            detail=detail,
        )

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "decision": self.decision,
            "reason": self.reason.value,
            "severity": self.severity.value,
            "source": self.source,
            "detail": self.detail,
            "decided_at": self.decided_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "StateDecision":
        return cls(
            decision=data["decision"],
            reason=StateReasonCode(data["reason"]),
            severity=Severity(data["severity"]),
            source=data.get("source", "control-plane"),
            detail=data.get("detail", ""),
            decided_at=datetime.fromisoformat(data["decided_at"])
            if data.get("decided_at")
            else None,
        )
