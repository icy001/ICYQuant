"""Pending Handler — Handles orders in pending/submitted state.

Manages orders that have been submitted but not yet acknowledged
by the broker/exchange. Handles timeout and status polling.

Pipeline:
    Submitted Order → Pending Monitor → Timeout Detection → Recovery/Action
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

from services.oms.order.models import Order, OrderStatus
from services.oms.lifecycle.state_transition_validator import LifecycleStatus
from services.oms.lifecycle.transition_engine import TransitionEngine, TransitionEventType

logger = logging.getLogger(__name__)


@dataclass
class PendingResult:
    """Result of pending order handling."""
    order_id: str
    status: str = "pending"
    time_in_pending_ms: float = 0.0
    timed_out: bool = False
    action: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "status": self.status,
            "time_in_pending_ms": self.time_in_pending_ms,
            "timed_out": self.timed_out,
            "action": self.action,
            "timestamp": self.timestamp.isoformat(),
        }


class PendingHandler:
    """Handles orders in pending (SUBMITTED) state.

    Monitors orders awaiting broker acknowledgment and handles
    timeouts. In production, this would poll broker status APIs
    and trigger recovery for stuck orders.

    Usage::

        handler = PendingHandler(transition_engine)
        result = await handler.monitor(order, submitted_at)
        if result.timed_out:
            await handler.handle_timeout(order)
    """

    def __init__(
        self,
        transition_engine: TransitionEngine,
        ack_timeout_seconds: int = 30,
    ) -> None:
        """Initialize pending handler.

        Args:
            transition_engine: Transition engine for state changes
            ack_timeout_seconds: Timeout for ACK response
        """
        self._engine = transition_engine
        self._ack_timeout = ack_timeout_seconds
        # Track submission times
        self._submitted_at: dict[str, datetime] = {}

    async def monitor(
        self,
        order: Order,
        submitted_at: Optional[datetime] = None,
    ) -> PendingResult:
        """Monitor an order in pending state.

        Args:
            order: Order to monitor
            submitted_at: When the order was submitted

        Returns:
            PendingResult with status and timing
        """
        submit_time = submitted_at or order.submitted_at or datetime.now(timezone.utc)
        self._submitted_at[order.order_id] = submit_time

        elapsed = (datetime.now(timezone.utc) - submit_time).total_seconds() * 1000
        timed_out = elapsed > (self._ack_timeout * 1000)

        if timed_out:
            logger.warning(
                f"Order {order.order_id} pending timeout: "
                f"elapsed={elapsed:.0f}ms > {self._ack_timeout * 1000}ms"
            )
            return PendingResult(
                order_id=order.order_id,
                status="timeout",
                time_in_pending_ms=elapsed,
                timed_out=True,
                action="timeout_detected",
            )

        logger.debug(
            f"Order {order.order_id} still pending: elapsed={elapsed:.0f}ms"
        )
        return PendingResult(
            order_id=order.order_id,
            status="pending",
            time_in_pending_ms=elapsed,
            timed_out=False,
        )

    async def handle_timeout(self, order: Order) -> None:
        """Handle a pending order timeout.

        In production, this would cancel the order and notify
        the strategy. Currently marks for investigation.

        Args:
            order: Order that timed out
        """
        logger.warning(
            f"Handling timeout for order {order.order_id}: "
            f"symbol={order.symbol}, submitted to {order.broker}"
        )

    def clear(self, order_id: str) -> None:
        """Clear tracking for an acknowledged order.

        Args:
            order_id: Order that has been acknowledged
        """
        self._submitted_at.pop(order_id, None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pending_orders": len(self._submitted_at),
            "ack_timeout_seconds": self._ack_timeout,
        }
