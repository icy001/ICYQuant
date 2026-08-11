"""OrderProjection — the read model derived from events.

A projection is a cached view of order state, NOT the source of truth.
The event store is the source of truth. Projections can be rebuilt
at any time by replaying events.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from services.oms.domain.order_status import OrderStatus


@dataclass
class OrderProjection:
    """A read model projection of order state.

    Fields:
        order_id: Order identifier.
        status: Current order status.
        symbol: Trading symbol.
        side: BUY/SELL.
        original_quantity: Original order quantity.
        filled_quantity: Cumulative filled quantity.
        remaining_quantity: Remaining quantity.
        cancelled_quantity: Cancelled quantity.
        average_price: Volume-weighted average fill price.
        last_event_sequence: Sequence of the last applied event.
        last_event_hash: Hash of the last applied event.
        lineage_id: Control lineage ID.
        flow_id: Business flow ID.
        certificate_id: Admission certificate ID.
        updated_at: Last update timestamp.
        is_stale: True if projection may be behind the event store.
    """

    order_id: str = ""
    status: OrderStatus = OrderStatus.RECEIVED
    symbol: str = ""
    side: str = ""
    order_type: str = ""

    original_quantity: float = 0.0
    filled_quantity: float = 0.0
    remaining_quantity: float = 0.0
    cancelled_quantity: float = 0.0
    average_price: float = 0.0

    last_event_sequence: int = 0
    last_event_hash: str = ""

    lineage_id: str = ""
    flow_id: str = ""
    certificate_id: str = ""

    updated_at: float = field(default_factory=lambda: __import__("time").time())
    is_stale: bool = False

    @property
    def is_terminal(self) -> bool:
        return self.status.is_terminal

    @property
    def fill_pct(self) -> float:
        if self.original_quantity <= 0:
            return 0.0
        return (self.filled_quantity / self.original_quantity) * 100.0

    @property
    def lag(self) -> int:
        """Projection lag — should be compared against the event store."""
        return 0  # computed externally

    def to_dict(self) -> Dict[str, Any]:
        return {
            "order_id": self.order_id,
            "status": self.status.name,
            "symbol": self.symbol,
            "side": self.side,
            "order_type": self.order_type,
            "original_quantity": self.original_quantity,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "cancelled_quantity": self.cancelled_quantity,
            "average_price": self.average_price,
            "last_event_sequence": self.last_event_sequence,
            "last_event_hash": self.last_event_hash,
            "lineage_id": self.lineage_id,
            "flow_id": self.flow_id,
            "certificate_id": self.certificate_id,
            "updated_at": self.updated_at,
            "is_stale": self.is_stale,
        }

    @classmethod
    def empty(cls, order_id: str = "") -> "OrderProjection":
        return cls(order_id=order_id)

    def mark_stale(self) -> None:
        self.is_stale = True

    def mark_fresh(self) -> None:
        self.is_stale = False
