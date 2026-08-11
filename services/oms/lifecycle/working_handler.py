"""Working Handler — Handles orders in working state at the exchange.

Manages orders that are active at the exchange. Monitors for
fills, cancellations, and state changes from the broker.

Pipeline:
    ACK Order → Working State → Fill Monitor / Cancel Monitor
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from services.oms.order.models import Order
from services.oms.lifecycle.state_transition_validator import LifecycleStatus
from services.oms.lifecycle.transition_engine import TransitionEngine

logger = logging.getLogger(__name__)


@dataclass
class WorkingResult:
    """Result of working order processing."""
    order_id: str
    status: str = "working"
    broker_order_id: str = ""
    time_in_working_ms: float = 0.0
    last_check: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "status": self.status,
            "broker_order_id": self.broker_order_id,
            "time_in_working_ms": self.time_in_working_ms,
            "last_check": self.last_check.isoformat(),
            "metadata": self.metadata,
        }


class WorkingHandler:
    """Handles orders in the WORKING state at the exchange.

    Manages active orders, monitoring for execution reports (fills),
    cancellations, and state changes from the broker.

    Usage::

        handler = WorkingHandler(transition_engine)
        result = await handler.monitor(order)
        if order.filled_quantity > 0:
            await fill_handler.handle_fill(order, fill_data)
    """

    def __init__(self, transition_engine: TransitionEngine) -> None:
        self._engine = transition_engine
        # Track when orders entered working state
        self._working_since: dict[str, datetime] = {}

    async def monitor(self, order: Order) -> WorkingResult:
        """Monitor an order in working state.

        Args:
            order: Order currently working at exchange

        Returns:
            WorkingResult with current status
        """
        if order.order_id not in self._working_since:
            self._working_since[order.order_id] = datetime.now(timezone.utc)

        elapsed = (
            datetime.now(timezone.utc) - self._working_since[order.order_id]
        ).total_seconds() * 1000

        status = LifecycleStatus(order.status.value)
        if not status.is_active:
            logger.warning(
                f"Order {order.order_id} is no longer active: {status.value}"
            )
            return WorkingResult(
                order_id=order.order_id,
                status="inactive",
                time_in_working_ms=elapsed,
            )

        return WorkingResult(
            order_id=order.order_id,
            status="working",
            broker_order_id=getattr(order, "broker_order_id", ""),
            time_in_working_ms=elapsed,
            metadata={
                "filled_qty": order.filled_quantity,
                "remaining_qty": order.remaining_quantity,
                "fill_pct": order.fill_pct,
            },
        )

    async def on_broker_status(
        self,
        order: Order,
        broker_status: str,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        """Handle a broker status update for a working order.

        Args:
            order: Working order
            broker_status: Status reported by broker
            details: Additional status details
        """
        logger.info(
            f"Broker status update for order {order.order_id}: "
            f"{broker_status}, details={details}"
        )

    def clear(self, order_id: str) -> None:
        """Clear working state tracking.

        Args:
            order_id: Order that is no longer working
        """
        self._working_since.pop(order_id, None)

    def to_dict(self) -> dict[str, Any]:
        return {
            "working_orders": len(self._working_since),
        }
