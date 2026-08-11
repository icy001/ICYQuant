"""
Order Intent
============
Standardized Order Intent object — the single output format
of the Strategy Platform, consumed by the Risk Engine and OMS.

Format:
    Intent ID, Portfolio ID, Instrument, Direction,
    Quantity, Target Weight, Priority, Confidence, Reason
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


class IntentStatus(str, Enum):
    """Status of an order intent."""

    DRAFT = "draft"
    PENDING_RISK = "pending_risk"
    APPROVED = "approved"
    REJECTED = "rejected"
    ROUTED = "routed"
    EXECUTED = "executed"
    PARTIALLY_EXECUTED = "partially_executed"
    CANCELLED = "cancelled"
    EXPIRED = "expired"
    ERROR = "error"


class IntentSide(str, Enum):
    """Side/direction of an order intent."""

    BUY = "BUY"
    SELL = "SELL"
    BUY_TO_COVER = "BUY_TO_COVER"
    SELL_SHORT = "SELL_SHORT"


class IntentType(str, Enum):
    """Type of order intent."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"
    TWAP = "TWAP"
    VWAP = "VWAP"
    ICEBERG = "ICEBERG"


@dataclass
class OrderIntent:
    """
    Standardized Order Intent.

    This is the ONLY output format from the Strategy Platform.
    All downstream systems (Risk Engine, OMS) consume this format.
    """

    # Identity
    intent_id: str = field(default_factory=lambda: f"oi_{uuid4().hex[:12]}")
    batch_id: str = ""
    portfolio_id: str = ""
    strategy_id: str = ""
    signal_id: str = ""
    decision_id: str = ""

    # Instrument
    instrument: str = ""
    instrument_type: str = ""  # EQUITY, FUTURE, OPTION, etc.
    exchange: str = ""

    # Order details
    side: IntentSide = IntentSide.BUY
    intent_type: IntentType = IntentType.MARKET
    quantity: float = 0.0
    limit_price: Optional[float] = None
    stop_price: Optional[float] = None

    # Portfolio context
    target_weight: float = 0.0
    current_weight: float = 0.0
    allocated_capital: float = 0.0

    # Metadata
    priority: int = 5
    confidence: float = 0.0
    reason: str = ""
    explanation: Optional[str] = None

    # Risk pre-checks
    risk_score: float = 0.0
    risk_checked: bool = False

    # Routing
    destination: str = ""  # Target OMS / execution venue
    route_status: str = ""

    # Lifecycle
    status: IntentStatus = IntentStatus.DRAFT
    time_in_force: str = "DAY"  # DAY, GTC, IOC, FOK

    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    expires_at: Optional[datetime] = None
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # Extensibility
    tags: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @property
    def notional_value(self) -> float:
        """Estimated notional value of this intent."""
        if self.limit_price and self.quantity:
            return self.limit_price * self.quantity
        return self.allocated_capital

    def mark_status(self, status: IntentStatus, reason: str = "") -> None:
        """Transition the intent to a new status."""
        self.status = status
        self.updated_at = datetime.now(timezone.utc)
        if reason:
            self.reason = reason

    def is_active(self) -> bool:
        """Check if the intent is still active."""
        return self.status in (
            IntentStatus.DRAFT,
            IntentStatus.PENDING_RISK,
            IntentStatus.APPROVED,
            IntentStatus.ROUTED,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Serialize to dict for downstream consumption."""
        return {
            "intent_id": self.intent_id,
            "batch_id": self.batch_id,
            "portfolio_id": self.portfolio_id,
            "strategy_id": self.strategy_id,
            "signal_id": self.signal_id,
            "decision_id": self.decision_id,
            "instrument": self.instrument,
            "instrument_type": self.instrument_type,
            "exchange": self.exchange,
            "side": self.side.value,
            "intent_type": self.intent_type.value,
            "quantity": self.quantity,
            "limit_price": self.limit_price,
            "stop_price": self.stop_price,
            "target_weight": self.target_weight,
            "current_weight": self.current_weight,
            "allocated_capital": self.allocated_capital,
            "priority": self.priority,
            "confidence": self.confidence,
            "reason": self.reason,
            "explanation": self.explanation,
            "risk_score": self.risk_score,
            "risk_checked": self.risk_checked,
            "destination": self.destination,
            "route_status": self.route_status,
            "status": self.status.value,
            "time_in_force": self.time_in_force,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "updated_at": self.updated_at.isoformat(),
            "tags": self.tags,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "OrderIntent":
        """Deserialize from dict."""
        intent = cls()
        intent.intent_id = data.get("intent_id", intent.intent_id)
        intent.batch_id = data.get("batch_id", "")
        intent.portfolio_id = data.get("portfolio_id", "")
        intent.strategy_id = data.get("strategy_id", "")
        intent.signal_id = data.get("signal_id", "")
        intent.decision_id = data.get("decision_id", "")
        intent.instrument = data.get("instrument", "")
        intent.instrument_type = data.get("instrument_type", "")
        intent.exchange = data.get("exchange", "")
        intent.side = IntentSide(data.get("side", "BUY"))
        intent.intent_type = IntentType(data.get("intent_type", "MARKET"))
        intent.quantity = data.get("quantity", 0.0)
        intent.limit_price = data.get("limit_price")
        intent.stop_price = data.get("stop_price")
        intent.target_weight = data.get("target_weight", 0.0)
        intent.current_weight = data.get("current_weight", 0.0)
        intent.allocated_capital = data.get("allocated_capital", 0.0)
        intent.priority = data.get("priority", 5)
        intent.confidence = data.get("confidence", 0.0)
        intent.reason = data.get("reason", "")
        intent.explanation = data.get("explanation")
        intent.risk_score = data.get("risk_score", 0.0)
        intent.risk_checked = data.get("risk_checked", False)
        intent.destination = data.get("destination", "")
        intent.route_status = data.get("route_status", "")
        intent.status = IntentStatus(data.get("status", "draft"))
        intent.time_in_force = data.get("time_in_force", "DAY")
        intent.tags = data.get("tags", [])
        intent.metadata = data.get("metadata", {})
        return intent


@dataclass
class IntentBatch:
    """A batch of order intents processed together."""

    batch_id: str = field(default_factory=lambda: f"ib_{uuid4().hex[:12]}")
    portfolio_id: str = ""
    intents: List[OrderIntent] = field(default_factory=list)
    total_notional: float = 0.0
    total_quantity: float = 0.0
    status: IntentStatus = IntentStatus.DRAFT
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def count(self) -> int:
        return len(self.intents)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "portfolio_id": self.portfolio_id,
            "intent_count": len(self.intents),
            "total_notional": self.total_notional,
            "total_quantity": self.total_quantity,
            "status": self.status.value,
            "intents": [i.to_dict() for i in self.intents],
            "created_at": self.created_at.isoformat(),
            "metadata": self.metadata,
        }
