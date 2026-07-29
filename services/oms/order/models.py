"""OMS Order Domain Models.

Defines the core order objects for the OMS/EMS integration layer:
- Order: Full order lifecycle with all fields required for institutional trading
- Enums: OrderStatus, OrderSide, OrderType, TimeInForce, OrderSource
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4


# =============================================================================
# Enums
# =============================================================================


class OrderStatus(str, Enum):
    """Order lifecycle status.

    The complete institutional order lifecycle:
    CREATED -> VALIDATED -> ROUTED -> SUBMITTED -> ACKNOWLEDGED
    -> PARTIALLY_FILLED -> FILLED
    Terminals: CANCELLED, REJECTED
    """

    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    ROUTED = "ROUTED"
    SUBMITTED = "SUBMITTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    PARTIALLY_FILLED = "PARTIALLY_FILLED"
    FILLED = "FILLED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


class OrderSide(str, Enum):
    """Order direction."""

    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    """Order type."""

    MARKET = "MARKET"
    LIMIT = "LIMIT"
    STOP = "STOP"
    STOP_LIMIT = "STOP_LIMIT"


class TimeInForce(str, Enum):
    """Time-in-force instructions."""

    DAY = "DAY"
    GTC = "GTC"          # Good-Til-Cancelled
    IOC = "IOC"          # Immediate-Or-Cancel
    FOK = "FOK"          # Fill-Or-Kill
    GTD = "GTD"          # Good-Til-Date


class OrderSource(str, Enum):
    """Origin of the order."""

    STRATEGY = "STRATEGY"
    MANUAL = "MANUAL"
    API = "API"
    RISK_ENGINE = "RISK_ENGINE"


# =============================================================================
# Dataclasses
# =============================================================================


@dataclass
class Order:
    """Core order domain object.

    Represents a single order through its entire lifecycle,
    from creation to settlement. Tracks filled quantity,
    execution details, and routing information.

    Example:
        order = Order(
            order_id="ORD_20260728_001",
            strategy_id="AI_Momentum",
            symbol="NVDA",
            side=OrderSide.BUY,
            quantity=10000,
            price=150.0,
        )
    """

    order_id: str = field(default_factory=lambda: str(uuid4()))
    strategy_id: str = ""
    symbol: str = ""
    side: OrderSide = OrderSide.BUY
    quantity: float = 0.0
    price: float = 0.0
    status: OrderStatus = OrderStatus.CREATED
    order_type: OrderType = OrderType.MARKET
    time_in_force: TimeInForce = TimeInForce.DAY
    source: OrderSource = OrderSource.STRATEGY

    # Execution tracking
    filled_quantity: float = 0.0
    average_fill_price: float = 0.0
    total_commission: float = 0.0

    # Routing info
    broker: str = ""
    market: str = ""
    route: str = ""

    # Timestamps
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None

    # Metadata
    tags: Dict[str, str] = field(default_factory=dict)
    notes: str = ""
    rejection_reason: str = ""

    # History log
    status_history: List[Dict[str, Any]] = field(default_factory=list)

    @property
    def remaining_quantity(self) -> float:
        """Quantity still to be filled."""
        return max(0.0, self.quantity - self.filled_quantity)

    @property
    def fill_pct(self) -> float:
        """Percentage of order that has been filled."""
        if self.quantity <= 0:
            return 0.0
        return self.filled_quantity / self.quantity

    @property
    def is_active(self) -> bool:
        """Whether the order is currently active in the market."""
        return self.status in (
            OrderStatus.SUBMITTED,
            OrderStatus.ACKNOWLEDGED,
            OrderStatus.PARTIALLY_FILLED,
        )

    @property
    def is_terminal(self) -> bool:
        """Whether the order is in a terminal (final) state."""
        return self.status in (
            OrderStatus.FILLED,
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
        )

    @property
    def notional_value(self) -> float:
        """Total notional value of the order."""
        if self.price > 0:
            return self.quantity * self.price
        return 0.0

    def record_status_change(self, from_status: OrderStatus, to_status: OrderStatus) -> None:
        """Record a status transition in the history log."""
        self.status_history.append({
            "from": from_status.value,
            "to": to_status.value,
            "timestamp": datetime.utcnow().isoformat(),
        })

    def to_dict(self) -> dict:
        """Serialize order to dictionary."""
        return {
            "order_id": self.order_id,
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "price": self.price,
            "status": self.status.value,
            "order_type": self.order_type.value,
            "time_in_force": self.time_in_force.value,
            "source": self.source.value,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "fill_pct": f"{self.fill_pct:.1%}",
            "average_fill_price": self.average_fill_price,
            "total_commission": self.total_commission,
            "broker": self.broker,
            "market": self.market,
            "route": self.route,
            "is_active": self.is_active,
            "is_terminal": self.is_terminal,
            "notional_value": self.notional_value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "rejection_reason": self.rejection_reason,
            "notes": self.notes,
        }
