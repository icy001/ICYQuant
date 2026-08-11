"""Child Order — Child order model for the Execution Management System.

A child order is a slice of a parent order produced by an execution algorithm.
Each child order is dispatched independently to the market via the broker gateway.

Lifecycle::

    PENDING → SUBMITTING → ACTIVE → PARTIAL_FILL → FILLED
                    ↓            ↓
               CANCELLING     CANCELLING
                    ↓            ↓
               CANCELLED     CANCELLED
                    ↓
               REJECTED

Usage::

    child = ChildOrder(
        parent_order_id="PO_001",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=100,
        price=150.0,
    )
    child.apply_fill(50, 149.95)
    child.apply_fill(50, 150.05)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ChildOrderStatus(str, Enum):
    """Child order execution status."""

    PENDING = "PENDING"
    SUBMITTING = "SUBMITTING"
    ACTIVE = "ACTIVE"
    PARTIAL_FILL = "PARTIAL_FILL"
    FILLED = "FILLED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"

    @property
    def is_terminal(self) -> bool:
        return self in (
            ChildOrderStatus.FILLED,
            ChildOrderStatus.CANCELLED,
            ChildOrderStatus.REJECTED,
            ChildOrderStatus.ERROR,
        )

    @property
    def is_active(self) -> bool:
        return self in (
            ChildOrderStatus.SUBMITTING,
            ChildOrderStatus.ACTIVE,
            ChildOrderStatus.PARTIAL_FILL,
        )


@dataclass
class ChildOrder:
    """A child order — a slice of a parent order.

    Represents a single order dispatched to the market. Child orders
    are created by execution algorithms and tracked independently.

    Attributes:
        order_id: Unique child order identifier
        parent_order_id: Parent order identifier
        symbol: Trading instrument symbol
        side: Buy or sell
        quantity: Order quantity
        remaining_quantity: Unfilled quantity
        filled_quantity: Cumulative filled quantity
        average_price: Volume-weighted average fill price
        price: Limit price (0 = market order)
        order_type: Order type (LIMIT, MARKET, etc.)
        status: Current order status
        version: Order version (for replacements)
        commission: Total commission
        venue: Execution venue
        created_at: Order creation time
        submitted_at: Time submitted to broker
        filled_at: Time fully filled
        slice_index: Position in parent order slice sequence
        metadata: Arbitrary metadata
    """

    order_id: str = field(default_factory=lambda: f"CHILD_{uuid.uuid4().hex[:12]}")
    parent_order_id: str = ""
    symbol: str = ""
    side: str = ""
    quantity: float = 0.0
    remaining_quantity: float = 0.0
    filled_quantity: float = 0.0
    average_price: float = 0.0
    price: float = 0.0
    order_type: str = "LIMIT"
    status: ChildOrderStatus = ChildOrderStatus.PENDING
    version: int = 1
    commission: float = 0.0
    venue: str = ""
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    submitted_at: Optional[datetime] = None
    filled_at: Optional[datetime] = None
    slice_index: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)

    # Status aliases for compatibility
    PENDING = ChildOrderStatus.PENDING
    SUBMITTING = ChildOrderStatus.SUBMITTING
    ACTIVE = ChildOrderStatus.ACTIVE
    PARTIAL_FILL = ChildOrderStatus.PARTIAL_FILL
    FILLED = ChildOrderStatus.FILLED
    CANCELLING = ChildOrderStatus.CANCELLING
    CANCELLED = ChildOrderStatus.CANCELLED
    REJECTED = ChildOrderStatus.REJECTED
    ERROR = ChildOrderStatus.ERROR

    @property
    def fill_pct(self) -> float:
        """Percentage of order filled."""
        if self.quantity <= 0:
            return 0.0
        return self.filled_quantity / self.quantity

    @property
    def is_filled(self) -> bool:
        """Whether the order is fully filled."""
        return self.status == ChildOrderStatus.FILLED

    @property
    def duration_seconds(self) -> float:
        """Time from submission to fill/cancel."""
        if not self.submitted_at:
            return 0.0
        end = self.filled_at or datetime.now(timezone.utc)
        return (end - self.submitted_at).total_seconds()

    def apply_fill(self, fill_qty: float, fill_price: float, commission: float = 0.0) -> bool:
        """Apply a fill to this child order.

        Uses weighted average price calculation.

        Args:
            fill_qty: Fill quantity
            fill_price: Fill price
            commission: Commission for this fill

        Returns:
            True if order is now fully filled
        """
        if fill_qty <= 0:
            return self.is_filled

        total_notional = self.average_price * self.filled_quantity
        new_notional = fill_qty * fill_price

        self.filled_quantity += fill_qty
        self.remaining_quantity = max(0.0, self.quantity - self.filled_quantity)
        self.commission += commission

        if self.filled_quantity > 0:
            self.average_price = (total_notional + new_notional) / self.filled_quantity

        # Update status
        if self.remaining_quantity <= 0:
            self.status = ChildOrderStatus.FILLED
            self.filled_at = datetime.now(timezone.utc)
            return True
        else:
            self.status = ChildOrderStatus.PARTIAL_FILL
            return False

    def submit(self) -> None:
        """Mark order as submitted."""
        self.submitted_at = datetime.now(timezone.utc)
        self.status = ChildOrderStatus.SUBMITTING

    def activate(self) -> None:
        """Mark order as active (acknowledged by broker)."""
        self.status = ChildOrderStatus.ACTIVE

    def to_dict(self) -> dict[str, Any]:
        """Serialize child order to dictionary."""
        return {
            "order_id": self.order_id,
            "parent_order_id": self.parent_order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "remaining_quantity": self.remaining_quantity,
            "filled_quantity": self.filled_quantity,
            "average_price": self.average_price,
            "price": self.price,
            "order_type": self.order_type,
            "status": self.status.value,
            "version": self.version,
            "fill_pct": self.fill_pct,
            "commission": self.commission,
            "venue": self.venue,
            "created_at": self.created_at.isoformat(),
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "filled_at": self.filled_at.isoformat() if self.filled_at else None,
            "slice_index": self.slice_index,
            "duration_seconds": self.duration_seconds,
        }
