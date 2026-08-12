"""
TradingBlocked — an order was denied by the Trading Gate.

Emitted whenever the gate returns DENY, carrying the full audit trail so we
can answer: "why was this order never sent to the broker?"

Example:

    order_id:      ORD-001
    strategy_id:   STRATEGY-ALPHA
    account_id:    ACCOUNT-001
    instrument_id: NVDA
    reason:        RISK_ENGINE_UNHEALTHY
    decision:      DENY
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional, Union

from ..trading_gate.gate_decision import GateDecision
from ..trading_gate.gate_reason import GateReason


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class TradingBlocked:
    event_type = "TRADING_BLOCKED"

    def __init__(
        self,
        order_id: str,
        reason: Union[GateReason, str],
        decision: Union[GateDecision, str] = GateDecision.DENY,
        strategy_id: str = "",
        account_id: str = "",
        instrument_id: str = "",
        correlation_id: str = "",
        blocked_at: Optional[datetime] = None,
    ) -> None:
        self.order_id = order_id
        self.strategy_id = strategy_id
        self.account_id = account_id
        self.instrument_id = instrument_id
        self.reason = GateReason(reason)
        self.decision = GateDecision(decision)
        self.correlation_id = correlation_id
        self.blocked_at = blocked_at or _utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "order_id": self.order_id,
            "strategy_id": self.strategy_id,
            "account_id": self.account_id,
            "instrument_id": self.instrument_id,
            "reason": self.reason.value,
            "decision": self.decision.value,
            "correlation_id": self.correlation_id,
            "blocked_at": self.blocked_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradingBlocked":
        blocked_at = data.get("blocked_at")
        return cls(
            order_id=data["order_id"],
            reason=data["reason"],
            decision=data.get("decision", "DENY"),
            strategy_id=data.get("strategy_id", ""),
            account_id=data.get("account_id", ""),
            instrument_id=data.get("instrument_id", ""),
            correlation_id=data.get("correlation_id", ""),
            blocked_at=datetime.fromisoformat(blocked_at) if blocked_at else None,
        )

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, TradingBlocked):
            return NotImplemented
        return self.to_dict() == other.to_dict()

    def __repr__(self) -> str:
        return f"TradingBlocked({self.order_id}: {self.reason.value})"
