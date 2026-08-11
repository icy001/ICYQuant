"""Fill Handler — Handles complete order fill events.

Processes final fill events that complete the order. Updates
the order to FILLED state with final execution details.

Pipeline:
    Final Fill Event → Mark Filled → Record Timestamp → Publish Fill → Audit

Key features:
- Final fill confirmation
- Complete fill audit trail
- Fill event broadcasting
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
from services.oms.lifecycle.partial_fill_handler import PartialFillHandler

logger = logging.getLogger(__name__)


@dataclass
class FillResult:
    """Result of a complete fill processing."""
    order_id: str
    success: bool = False
    filled_quantity: float = 0.0
    average_price: float = 0.0
    total_commission: float = 0.0
    fill_timestamp: Optional[datetime] = None
    reason: str = ""
    transition: Optional[TransitionResult] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "success": self.success,
            "filled_quantity": self.filled_quantity,
            "average_price": self.average_price,
            "total_commission": self.total_commission,
            "fill_timestamp": (
                self.fill_timestamp.isoformat() if self.fill_timestamp else None
            ),
            "reason": self.reason,
            "metadata": self.metadata,
        }


class FillHandler:
    """Handles complete fill events for orders.

    Processes the final fill that completes an order. Coordinates
    with PartialFillHandler for incremental fills and manages the
    final FILLED state transition.

    Usage::

        handler = FillHandler(transition_engine, partial_fill_handler, duplicate_detector)
        result = await handler.handle_fill(order, fill_id="FILL-FINAL")
    """

    def __init__(
        self,
        transition_engine: TransitionEngine,
        partial_fill_handler: PartialFillHandler,
        duplicate_detector: DuplicateEventDetector,
    ) -> None:
        self._engine = transition_engine
        self._partial_fill = partial_fill_handler
        self._duplicate = duplicate_detector

    async def handle_fill(
        self,
        order: Order,
        fill_id: str,
        final_price: Optional[float] = None,
        sequence_id: int = 0,
        payload: Optional[dict[str, Any]] = None,
    ) -> FillResult:
        """Process a complete fill for an order.

        Args:
            order: Order being filled
            fill_id: Unique fill identifier
            final_price: Final execution price (if provided)
            sequence_id: Sequence number
            payload: Additional fill data

        Returns:
            FillResult with final fill details
        """
        # Duplicate check
        dup = self._duplicate.check(fill_id, order.order_id)
        if dup.is_duplicate:
            logger.warning(f"Duplicate fill {fill_id} for order {order.order_id}")
            return FillResult(
                order_id=order.order_id,
                success=False,
                reason=f"Duplicate fill: {fill_id}",
            )

        # If there's remaining quantity to fill, process as partial
        remaining = order.remaining_quantity
        if remaining > 0 and final_price:
            await self._partial_fill.handle_fill(
                order=order,
                fill_quantity=remaining,
                fill_price=final_price,
                fill_id=fill_id,
                sequence_id=sequence_id,
                payload=payload,
            )

        # Execute final FILLED transition
        event = TransitionEvent(
            event_id=fill_id,
            order_id=order.order_id,
            event_type=TransitionEventType.FILL,
            from_status=LifecycleStatus(order.status.value),
            to_status=LifecycleStatus.FILLED,
            payload=payload or {},
        )

        transition_result = await self._engine.transition(order, event)

        order.filled_at = datetime.now(timezone.utc)

        logger.info(
            f"Order {order.order_id} fully filled: "
            f"qty={order.filled_quantity}, avg_price={order.average_fill_price:.4f}"
        )

        return FillResult(
            order_id=order.order_id,
            success=True,
            filled_quantity=order.filled_quantity,
            average_price=order.average_fill_price,
            total_commission=order.total_commission,
            fill_timestamp=order.filled_at,
            reason="Order filled",
            transition=transition_result,
            metadata=payload or {},
        )

    async def force_fill(
        self,
        order: Order,
        fill_price: Optional[float] = None,
        reason: str = "forced_fill",
    ) -> FillResult:
        """Force-fill an order (e.g., for reconciliation).

        Args:
            order: Order to force-fill
            fill_price: Price to use (defaults to order price)
            reason: Reason for forced fill

        Returns:
            FillResult with fill details
        """
        price = fill_price or order.price or order.average_fill_price
        if price <= 0:
            price = 0.0

        remaining = order.remaining_quantity
        if remaining > 0:
            # Simulate fill of remaining quantity
            old_notional = order.filled_quantity * order.average_fill_price
            new_notional = remaining * price
            total_qty = order.filled_quantity + remaining
            order.average_fill_price = (old_notional + new_notional) / total_qty if total_qty > 0 else 0
            order.filled_quantity = total_qty

        order.filled_at = datetime.now(timezone.utc)
        order.notes = f"{order.notes}\n[FORCE FILL] {reason}"

        event = TransitionEvent(
            event_id=f"force-fill-{order.order_id}",
            order_id=order.order_id,
            event_type=TransitionEventType.FILL,
            from_status=LifecycleStatus(order.status.value),
            to_status=LifecycleStatus.FILLED,
            payload={"forced": True, "reason": reason},
        )

        transition_result = await self._engine.transition(order, event)

        return FillResult(
            order_id=order.order_id,
            success=True,
            filled_quantity=order.filled_quantity,
            average_price=order.average_fill_price,
            total_commission=order.total_commission,
            fill_timestamp=order.filled_at,
            reason=reason,
            transition=transition_result,
        )
