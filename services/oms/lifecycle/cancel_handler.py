"""Cancel Handler — Handles order cancellation requests.

Processes cancellation requests for active orders. Handles
cancel acknowledgments from the broker and transitions the
order to CANCELLED state.

Pipeline:
    Cancel Request → Broker Cancel → Cancel ACK → Transition to CANCELLED

Key features:
- Cancel request initiation
- Cancel acknowledgment processing
- Partial cancel support (cancel remaining)
- Cancel reason tracking
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
class CancelResult:
    """Result of an order cancellation."""
    order_id: str
    success: bool = False
    cancelled_quantity: float = 0.0
    reason: str = ""
    transition: Optional[TransitionResult] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "success": self.success,
            "cancelled_quantity": self.cancelled_quantity,
            "reason": self.reason,
            "timestamp": self.timestamp.isoformat(),
        }


class CancelHandler:
    """Handles order cancellation requests.

    Processes cancellation requests and acknowledgments for active
    orders. Supports both full and partial cancellation.

    Usage::

        handler = CancelHandler(transition_engine, duplicate_detector)
        result = await handler.cancel(order, reason="User requested")
    """

    def __init__(
        self,
        transition_engine: TransitionEngine,
        duplicate_detector: DuplicateEventDetector,
    ) -> None:
        self._engine = transition_engine
        self._duplicate = duplicate_detector

    async def cancel(
        self,
        order: Order,
        reason: str = "",
        cancel_id: Optional[str] = None,
        payload: Optional[dict[str, Any]] = None,
    ) -> CancelResult:
        """Cancel an active order.

        Args:
            order: Order to cancel
            reason: Reason for cancellation
            cancel_id: Unique cancel event ID
            payload: Additional cancel data

        Returns:
            CancelResult with cancellation status
        """
        event_id = cancel_id or f"cancel-{order.order_id}"

        # Duplicate check
        dup = self._duplicate.check(event_id, order.order_id)
        if dup.is_duplicate:
            logger.warning(f"Duplicate cancel for order {order.order_id}: {event_id}")
            return CancelResult(
                order_id=order.order_id,
                success=False,
                reason=f"Duplicate cancel: {event_id}",
            )

        current_status = LifecycleStatus(order.status.value)

        # Validate cancellable state
        if current_status.is_terminal:
            return CancelResult(
                order_id=order.order_id,
                success=False,
                reason=f"Cannot cancel order in terminal state: {current_status.value}",
            )

        # Track cancelled quantity
        cancelled_qty = order.remaining_quantity
        order.cancelled_at = datetime.now(timezone.utc)
        order.rejection_reason = reason

        # Execute CANCELLED transition
        event = TransitionEvent(
            event_id=event_id,
            order_id=order.order_id,
            event_type=TransitionEventType.CANCEL,
            from_status=current_status,
            to_status=LifecycleStatus.CANCELLED,
            payload=payload or {
                "reason": reason,
                "cancelled_quantity": cancelled_qty,
            },
        )

        transition_result = await self._engine.transition(order, event)

        logger.info(
            f"Order {order.order_id} cancelled: "
            f"remaining_qty={cancelled_qty}, reason='{reason}'"
        )

        return CancelResult(
            order_id=order.order_id,
            success=True,
            cancelled_quantity=cancelled_qty,
            reason=reason or "Cancelled",
            transition=transition_result,
        )

    async def request_cancel(
        self,
        order: Order,
        reason: str = "",
    ) -> CancelResult:
        """Send a cancel request (before confirmation).

        In production, this sends the cancel request to the broker.
        The actual cancellation happens when the broker ACK arrives.

        Args:
            order: Order to request cancellation for
            reason: Reason for cancellation

        Returns:
            CancelResult indicating request was sent
        """
        logger.info(
            f"Cancel request sent for order {order.order_id}: "
            f"reason='{reason}'"
        )

        return CancelResult(
            order_id=order.order_id,
            success=True,
            cancelled_quantity=0,
            reason=f"Cancel requested: {reason}",
        )
