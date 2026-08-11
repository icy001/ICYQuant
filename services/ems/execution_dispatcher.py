"""Execution Dispatcher — Child order dispatch to broker gateway.

Dispatches child orders to the appropriate broker or venue gateway.
Handles order submission, cancellation, and status tracking.

Pipeline::

    Algorithm → ExecutionDispatcher → Broker Gateway → Exchange

Usage::

    dispatcher = ExecutionDispatcher()
    await dispatcher.dispatch(child_order, context)
    await dispatcher.cancel(child_order)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from services.ems.child_order import ChildOrder
from services.ems.execution_context import ExecutionContext
from services.ems.execution_controller import ExecutionController

logger = logging.getLogger(__name__)


class ExecutionDispatcher:
    """Child order dispatcher to broker gateway.

    Manages the submission and lifecycle of child orders through the
    broker gateway layer. Handles rate limiting and error recovery.

    Attributes:
        controller: Execution controller for rate limiting
        _pending_orders: Currently pending dispatch operations
    """

    def __init__(self, controller: Optional[ExecutionController] = None) -> None:
        self.controller = controller or ExecutionController()
        self._pending_orders: dict[str, ChildOrder] = {}

    async def dispatch(self, child: ChildOrder, context: ExecutionContext) -> bool:
        """Dispatch a child order to the broker.

        Applies rate limiting and circuit breaker protection before
        submitting the order.

        Args:
            child: Child order to dispatch
            context: Execution context

        Returns:
            True if dispatched successfully
        """
        # Check circuit breaker
        if self.controller.is_circuit_open:
            logger.warning("Circuit breaker open, dispatch rejected: child=%s", child.order_id)
            return False

        # Rate limiting
        if not self.controller.allow_dispatch():
            await self.controller.throttle_dispatch()

        # Acquire concurrency slot
        acquired = await self.controller.acquire()
        if not acquired:
            logger.warning("Concurrency slot unavailable: child=%s", child.order_id)
            return False

        try:
            # TODO: Actual broker gateway dispatch in Part 1.4
            # For now, simulate successful dispatch
            self._pending_orders[child.order_id] = child
            child.status = child.ACTIVE

            self.controller.record_success()
            logger.debug(
                "Child order dispatched: child=%s qty=%.0f venue=%s",
                child.order_id,
                child.quantity,
                child.venue or "default",
            )
            return True

        except Exception as e:
            self.controller.record_failure()
            logger.error("Dispatch failed: child=%s error=%s", child.order_id, e)
            return False
        finally:
            self.controller.release()

    async def cancel(self, child: ChildOrder) -> bool:
        """Cancel a dispatched child order.

        Args:
            child: Child order to cancel

        Returns:
            True if cancellation submitted successfully
        """
        if child.order_id not in self._pending_orders:
            logger.warning("Cannot cancel unknown order: child=%s", child.order_id)
            return False

        try:
            # TODO: Actual broker gateway cancel in Part 1.4
            child.status = child.CANCELLED
            self._pending_orders.pop(child.order_id, None)
            logger.debug("Child order cancelled: child=%s", child.order_id)
            return True
        except Exception as e:
            logger.error("Cancel failed: child=%s error=%s", child.order_id, e)
            return False

    async def get_pending_orders(self) -> list[ChildOrder]:
        """Get all pending child orders.

        Returns:
            List of pending child orders
        """
        return list(self._pending_orders.values())

    async def get_pending_count(self) -> int:
        """Get count of pending child orders.

        Returns:
            Number of pending child orders
        """
        return len(self._pending_orders)

    def to_dict(self) -> dict[str, Any]:
        """Serialize dispatcher state."""
        return {
            "pending_orders": len(self._pending_orders),
            "controller": self.controller.to_dict(),
        }
