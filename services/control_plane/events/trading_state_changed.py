"""
TRADING_STATE_CHANGED event.

Emitted whenever the trading permission level changes:

    TRADING_READY → TRADING_DEGRADED
    event: {
        previous_state: TRADING_READY
        new_state:      TRADING_DEGRADED
        reason:         POSITION_MISMATCH
    }

Downstream consumers: OMS, Risk, UI, Alerting, Audit.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from ..domain.system_state import StateReasonCode
from ..domain.trading_state import TradingState


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class TradingStateChanged:
    """Event emitted when the trading state changes."""

    previous_state: TradingState
    new_state: TradingState
    reason: StateReasonCode
    gate_decision: str = ""
    source: str = "control-plane"
    event_type: str = "TRADING_STATE_CHANGED"
    event_id: str = ""
    detail: str = ""
    occurred_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.event_id:
            self.event_id = f"EVT-{uuid.uuid4().hex[:12].upper()}"
        if self.occurred_at is None:
            self.occurred_at = _utcnow()

    @classmethod
    def from_change(
        cls,
        previous_state: TradingState,
        new_state: TradingState,
        reason: StateReasonCode,
        gate_decision: str = "",
        source: str = "control-plane",
        detail: str = "",
        occurred_at: Optional[datetime] = None,
    ) -> "TradingStateChanged":
        return cls(
            previous_state=previous_state,
            new_state=new_state,
            reason=reason,
            gate_decision=gate_decision,
            source=source,
            detail=detail,
            occurred_at=occurred_at,
        )

    # -- serialization ----------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_type": self.event_type,
            "event_id": self.event_id,
            "previous_state": self.previous_state.value,
            "new_state": self.new_state.value,
            "reason": self.reason.value,
            "gate_decision": self.gate_decision,
            "source": self.source,
            "detail": self.detail,
            "occurred_at": self.occurred_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "TradingStateChanged":
        return cls(
            event_id=data.get("event_id", ""),
            previous_state=TradingState(data["previous_state"]),
            new_state=TradingState(data["new_state"]),
            reason=StateReasonCode(data["reason"]),
            gate_decision=data.get("gate_decision", ""),
            source=data.get("source", "control-plane"),
            detail=data.get("detail", ""),
            occurred_at=datetime.fromisoformat(data["occurred_at"])
            if data.get("occurred_at")
            else None,
        )
