"""
TradingGateChanged — the gate decision for an order changed (ALLOW ↔ DENY).

Example:

    order_id:          ORD-001
    previous_decision: ALLOW
    current_decision:  DENY
    reason:            RISK_ENGINE_UNHEALTHY
    policy_version:    trading-policy-v1.3
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from ..trading_gate.gate_decision import GateDecision
from ..trading_gate.gate_reason import GateReason


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TradingGateChanged:
    event_type = "TRADING_GATE_CHANGED"

    def __init__(
        self,
        order_id: str,
        previous_decision: Union[GateDecision, str],
        current_decision: Union[GateDecision, str],
        reason: Union[GateReason, str],
        policy_version: str = "",
        correlation_id: str = "",
        changed_at: Optional[datetime] = None,
    ) -> None:
        self.order_id = order_id
        self.previous_decision = GateDecision(previous_decision)
        self.current_decision = GateDecision(current_decision)
        self.reason = GateReason(reason)
        self.policy_version = policy_version
        self.correlation_id = correlation_id
        self.changed_at = changed_at or _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "order_id": self.order_id,
            "previous_decision": self.previous_decision.value,
            "current_decision": self.current_decision.value,
            "reason": self.reason.value,
            "policy_version": self.policy_version,
            "correlation_id": self.correlation_id,
            "changed_at": self.changed_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradingGateChanged":
        changed_at = data.get("changed_at")
        return cls(
            order_id=data["order_id"],
            previous_decision=data["previous_decision"],
            current_decision=data["current_decision"],
            reason=data["reason"],
            policy_version=data.get("policy_version", ""),
            correlation_id=data.get("correlation_id", ""),
            changed_at=datetime.fromisoformat(changed_at) if changed_at else None,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TradingGateChanged):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return (
            f"TradingGateChanged({self.order_id}: "
            f"{self.previous_decision.value} → {self.current_decision.value})"
        )
