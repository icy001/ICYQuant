"""Parent Order — Parent order model for the Execution Management System.

A parent order represents the original order intent that is decomposed
into multiple child orders for execution. The parent order tracks the
aggregate state of all its child orders.

Lifecycle::

    PENDING → SUBMITTING → ACTIVE → COMPLETING → COMPLETED
                    ↓            ↓
               CANCELLING     PAUSED
                    ↓            ↓
               CANCELLED     RESUMING → ACTIVE

Usage::

    parent = ParentOrder(
        parent_order_id="PO_001",
        oms_order_id="ORDER_001",
        symbol="AAPL",
        side=OrderSide.BUY,
        quantity=10000,
        strategy="TWAP",
    )
    parent.add_child(child_order)
    parent.apply_fill(500, 150.0)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional


class ParentOrderStatus(str, Enum):
    """Parent order execution status."""

    PENDING = "PENDING"
    SUBMITTING = "SUBMITTING"
    ACTIVE = "ACTIVE"
    PAUSED = "PAUSED"
    RESUMING = "RESUMING"
    COMPLETING = "COMPLETING"
    COMPLETED = "COMPLETED"
    CANCELLING = "CANCELLING"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"
    ERROR = "ERROR"

    @property
    def is_terminal(self) -> bool:
        return self in (
            ParentOrderStatus.COMPLETED,
            ParentOrderStatus.CANCELLED,
            ParentOrderStatus.REJECTED,
            ParentOrderStatus.ERROR,
        )

    @property
    def is_active(self) -> bool:
        return self in (
            ParentOrderStatus.SUBMITTING,
            ParentOrderStatus.ACTIVE,
            ParentOrderStatus.RESUMING,
        )


@dataclass
class ParentOrder:
    """A parent order that is decomposed into child orders for execution.

    Tracks the aggregate state across all child orders including total
    fill quantity, average price, and execution progress.

    Attributes:
        parent_order_id: Unique parent order identifier
        oms_order_id: Reference to originating OMS order
        symbol: Trading instrument symbol
        side: Buy or sell
        quantity: Total order quantity
        remaining_quantity: Unfilled quantity
        filled_quantity: Cumulative filled quantity
        average_price: Volume-weighted average fill price
        status: Current execution status
        strategy: Execution algorithm name
        child_order_ids: List of child order IDs
        active_children: Count of currently active child orders
        filled_children: Count of fully filled child orders
        benchmark_price: Arrival price benchmark
        commission: Total commission paid
        created_at: Order creation time
        started_at: Execution start time
        completed_at: Execution completion time
        venue: Target execution venue
        metadata: Arbitrary metadata
    """

    parent_order_id: str = field(default_factory=lambda: f"PO_{uuid.uuid4().hex[:12]}")
    oms_order_id: str = ""
    symbol: str = ""
    side: str = ""
    quantity: float = 0.0
    remaining_quantity: float = 0.0
    filled_quantity: float = 0.0
    average_price: float = 0.0
    status: ParentOrderStatus = ParentOrderStatus.PENDING
    strategy: str = ""
    child_order_ids: list[str] = field(default_factory=list)
    active_children: int = 0
    filled_children: int = 0
    benchmark_price: float = 0.0
    commission: float = 0.0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    venue: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def fill_pct(self) -> float:
        """Percentage of order filled."""
        if self.quantity <= 0:
            return 0.0
        return self.filled_quantity / self.quantity

    @property
    def is_complete(self) -> bool:
        """Whether the order is fully executed."""
        return self.status.is_terminal

    @property
    def slippage_bps(self) -> float:
        """Slippage in basis points vs benchmark."""
        if self.benchmark_price <= 0 or self.average_price <= 0:
            return 0.0
        return (self.average_price - self.benchmark_price) / self.benchmark_price * 10000

    @property
    def duration_seconds(self) -> float:
        """Execution duration in seconds."""
        if not self.started_at:
            return 0.0
        end = self.completed_at or datetime.now(timezone.utc)
        return (end - self.started_at).total_seconds()

    def add_child(self, child_order_id: str) -> None:
        """Register a new child order.

        Args:
            child_order_id: Child order identifier
        """
        if child_order_id not in self.child_order_ids:
            self.child_order_ids.append(child_order_id)
        self.active_children += 1

    def child_filled(self, child_order_id: str) -> None:
        """Mark a child order as filled.

        Args:
            child_order_id: Child order identifier
        """
        self.filled_children += 1
        self.active_children = max(0, self.active_children - 1)

    def child_cancelled(self, child_order_id: str) -> None:
        """Mark a child order as cancelled.

        Args:
            child_order_id: Child order identifier
        """
        self.active_children = max(0, self.active_children - 1)

    def apply_fill(self, fill_qty: float, fill_price: float, commission: float = 0.0) -> None:
        """Apply a fill from a child order to aggregate metrics.

        Uses weighted average price calculation for multiple fills.

        Args:
            fill_qty: Fill quantity
            fill_price: Fill price
            commission: Commission for this fill
        """
        if fill_qty <= 0:
            return

        total_notional = self.average_price * self.filled_quantity
        new_notional = fill_qty * fill_price

        self.filled_quantity += fill_qty
        self.remaining_quantity = max(0.0, self.quantity - self.filled_quantity)
        self.commission += commission

        if self.filled_quantity > 0:
            self.average_price = (total_notional + new_notional) / self.filled_quantity

    def start(self) -> None:
        """Mark parent order as started."""
        self.started_at = datetime.now(timezone.utc)
        self.status = ParentOrderStatus.ACTIVE

    def complete(self) -> None:
        """Mark parent order as completed."""
        self.completed_at = datetime.now(timezone.utc)
        self.status = ParentOrderStatus.COMPLETED

    def cancel(self) -> None:
        """Mark parent order as cancelled."""
        self.status = ParentOrderStatus.CANCELLED
        if not self.completed_at:
            self.completed_at = datetime.now(timezone.utc)

    def to_dict(self) -> dict[str, Any]:
        """Serialize parent order to dictionary."""
        return {
            "parent_order_id": self.parent_order_id,
            "oms_order_id": self.oms_order_id,
            "symbol": self.symbol,
            "side": self.side,
            "quantity": self.quantity,
            "remaining_quantity": self.remaining_quantity,
            "filled_quantity": self.filled_quantity,
            "average_price": self.average_price,
            "status": self.status.value,
            "strategy": self.strategy,
            "fill_pct": self.fill_pct,
            "slippage_bps": self.slippage_bps,
            "child_order_ids": self.child_order_ids,
            "active_children": self.active_children,
            "filled_children": self.filled_children,
            "benchmark_price": self.benchmark_price,
            "commission": self.commission,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration_seconds": self.duration_seconds,
            "venue": self.venue,
        }
