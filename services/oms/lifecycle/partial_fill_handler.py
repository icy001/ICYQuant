"""Partial Fill Handler — Handles incremental trade executions.

Processes partial fill events from broker gateways. Accumulates
filled quantity, calculates average price, and tracks remaining
quantity. Supports multiple partial fills before final fill.

Pipeline:
    Fill Event → Update Filled Qty → Update Avg Price → Update Remaining Qty → Publish

Key features:
- Weighted average price calculation across fills
- Cumulative fill tracking
- Remaining quantity management
- Fill event publishing
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from services.oms.order.models import Order, OrderStatus
from services.oms.lifecycle.state_transition_validator import LifecycleStatus
from services.oms.lifecycle.transition_engine import (
    TransitionEngine,
    TransitionEvent,
    TransitionEventType,
    TransitionResult,
)
from services.oms.lifecycle.duplicate_event_detector import DuplicateEventDetector

logger = logging.getLogger(__name__)


@dataclass
class PartialFillResult:
    """Result of a partial fill processing."""
    order_id: str
    fill_quantity: float = 0.0
    fill_price: float = 0.0
    cumulative_filled: float = 0.0
    remaining_quantity: float = 0.0
    average_fill_price: float = 0.0
    fill_pct: float = 0.0
    transition: Optional[TransitionResult] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def is_complete(self) -> bool:
        """Whether the order is fully filled."""
        return self.remaining_quantity <= 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "fill_quantity": self.fill_quantity,
            "fill_price": self.fill_price,
            "cumulative_filled": self.cumulative_filled,
            "remaining_quantity": self.remaining_quantity,
            "average_fill_price": self.average_fill_price,
            "fill_pct": f"{self.fill_pct:.2%}",
            "is_complete": self.is_complete,
            "timestamp": self.timestamp.isoformat(),
        }


class PartialFillHandler:
    """Handles partial fill (trade execution) events.

    Processes incremental fill events from broker gateways. Updates
    the order's filled quantity and average price using weighted
    average calculation.

    Usage::

        handler = PartialFillHandler(transition_engine, duplicate_detector)
        result = await handler.handle_fill(
            order, fill_qty=100, fill_price=150.50, fill_id="FILL-001"
        )
    """

    def __init__(
        self,
        transition_engine: TransitionEngine,
        duplicate_detector: DuplicateEventDetector,
    ) -> None:
        self._engine = transition_engine
        self._duplicate = duplicate_detector

    async def handle_fill(
        self,
        order: Order,
        fill_quantity: float,
        fill_price: float,
        fill_id: str,
        sequence_id: int = 0,
        commission: float = 0.0,
        payload: Optional[dict[str, Any]] = None,
    ) -> PartialFillResult:
        """Process a partial fill event.

        Args:
            order: Order being filled
            fill_quantity: Quantity filled in this execution
            fill_price: Execution price
            fill_id: Unique fill/trade identifier
            sequence_id: Sequence number for ordering
            commission: Commission for this fill
            payload: Additional fill data

        Returns:
            PartialFillResult with updated fill state
        """
        # Duplicate check
        dup = self._duplicate.check(fill_id, order.order_id)
        if dup.is_duplicate:
            logger.warning(
                f"Duplicate fill {fill_id} for order {order.order_id}, discarding"
            )
            return PartialFillResult(
                order_id=order.order_id,
                fill_quantity=0,
                fill_price=fill_price,
                cumulative_filled=order.filled_quantity,
                remaining_quantity=order.remaining_quantity,
                average_fill_price=order.average_fill_price,
                fill_pct=order.fill_pct,
            )

        # Validate fill quantity
        if fill_quantity <= 0:
            logger.error(
                f"Invalid fill quantity {fill_quantity} for order {order.order_id}"
            )
            return PartialFillResult(
                order_id=order.order_id,
                fill_quantity=0,
                fill_price=fill_price,
                cumulative_filled=order.filled_quantity,
                remaining_quantity=order.remaining_quantity,
                average_fill_price=order.average_fill_price,
                fill_pct=order.fill_pct,
            )

        # Calculate new cumulative filled
        new_filled = order.filled_quantity + fill_quantity

        # Weighted average price: (old_qty * old_avg + new_qty * new_price) / total_qty
        if new_filled > 0:
            old_notional = order.filled_quantity * order.average_fill_price
            new_notional = fill_quantity * fill_price
            order.average_fill_price = (old_notional + new_notional) / new_filled

        # Update order fill state
        order.filled_quantity = new_filled
        order.total_commission += commission

        # Determine new status
        if order.remaining_quantity <= 0:
            new_status = LifecycleStatus.FILLED
            order.filled_at = datetime.now(timezone.utc)
        else:
            new_status = LifecycleStatus.PARTIALLY_FILLED

        # Execute transition
        event = TransitionEvent(
            event_id=fill_id,
            order_id=order.order_id,
            event_type=(
                TransitionEventType.FILL
                if new_status == LifecycleStatus.FILLED
                else TransitionEventType.PARTIAL_FILL
            ),
            from_status=LifecycleStatus(order.status.value),
            to_status=new_status,
            payload=payload or {
                "fill_quantity": fill_quantity,
                "fill_price": fill_price,
                "commission": commission,
            },
        )

        transition_result = await self._engine.transition(order, event)

        logger.info(
            f"Partial fill for order {order.order_id}: "
            f"qty={fill_quantity} @ {fill_price}, "
            f"cumulative={new_filled}/{order.quantity} ({order.fill_pct:.1%}), "
            f"avg_price={order.average_fill_price:.4f}"
        )

        return PartialFillResult(
            order_id=order.order_id,
            fill_quantity=fill_quantity,
            fill_price=fill_price,
            cumulative_filled=new_filled,
            remaining_quantity=order.remaining_quantity,
            average_fill_price=order.average_fill_price,
            fill_pct=order.fill_pct,
            transition=transition_result,
        )
