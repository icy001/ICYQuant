"""Child Order Manager — Child order lifecycle management.

Manages the lifecycle of child orders produced by execution algorithms.
Handles creation, dispatch, fill processing, and status tracking.

Pipeline::

    Algorithm → ChildOrderManager.create() → Dispatcher → Market

Usage::

    manager = ChildOrderManager(dispatcher=dispatcher)
    child = await manager.create_child(parent_order_id, quantity=100, price=150.0)
    await manager.submit(child)
    await manager.process_fill(child, qty=50, price=149.95)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from services.ems.child_order import ChildOrder, ChildOrderStatus
from services.ems.execution_dispatcher import ExecutionDispatcher

logger = logging.getLogger(__name__)


class ChildOrderManager:
    """Manages child order lifecycle from creation to fill.

    Handles child order creation, submission, fill processing, and
    cancellation. Coordinates with the ExecutionDispatcher for
    broker gateway communication.

    Attributes:
        dispatcher: Execution dispatcher for broker communication
        _orders: Map of child_order_id → ChildOrder
        _by_parent: Map of parent_order_id → list[child_order_id]
    """

    def __init__(self, dispatcher: Optional[ExecutionDispatcher] = None) -> None:
        self.dispatcher = dispatcher or ExecutionDispatcher()
        self._orders: dict[str, ChildOrder] = {}
        self._by_parent: dict[str, list[str]] = {}

    # ── Creation ───────────────────────────────────────────────────

    async def create_child(
        self,
        parent_order_id: str,
        quantity: float,
        price: float = 0.0,
        symbol: str = "",
        side: str = "",
        venue: str = "",
        slice_index: int = 0,
        **kwargs: Any,
    ) -> ChildOrder:
        """Create a new child order.

        Args:
            parent_order_id: Parent order identifier
            quantity: Order quantity
            price: Limit price (0 for market)
            symbol: Trading symbol
            side: Buy/sell
            venue: Target venue
            slice_index: Position in slice sequence
            **kwargs: Additional metadata

        Returns:
            Created ChildOrder
        """
        child = ChildOrder(
            parent_order_id=parent_order_id,
            symbol=symbol,
            side=side,
            quantity=quantity,
            remaining_quantity=quantity,
            price=price,
            venue=venue,
            slice_index=slice_index,
            metadata=kwargs,
        )

        self._orders[child.order_id] = child
        self._by_parent.setdefault(parent_order_id, []).append(child.order_id)

        logger.debug(
            "Child order created: %s parent=%s qty=%.0f price=%.2f slice=%d",
            child.order_id,
            parent_order_id,
            quantity,
            price,
            slice_index,
        )
        return child

    # ── Submission ─────────────────────────────────────────────────

    async def submit(self, child: ChildOrder) -> bool:
        """Submit a child order to the market.

        Args:
            child: Child order to submit

        Returns:
            True if submitted successfully
        """
        from services.ems.execution_context import ExecutionContext

        child.submit()

        # Build minimal context for dispatch
        context = ExecutionContext(
            parent_order=type("Order", (), {"order_id": child.parent_order_id, "quantity": child.quantity, "remaining_quantity": child.remaining_quantity})(),
            strategy="",
            venue=child.venue,
        )

        success = await self.dispatcher.dispatch(child, context)
        if success:
            child.activate()
        else:
            child.status = ChildOrderStatus.REJECTED

        return success

    # ── Fill Processing ────────────────────────────────────────────

    async def process_fill(
        self,
        child_order_id: str,
        fill_qty: float,
        fill_price: float,
        commission: float = 0.0,
    ) -> tuple[bool, bool]:
        """Process a fill for a child order.

        Args:
            child_order_id: Child order identifier
            fill_qty: Fill quantity
            fill_price: Fill price
            commission: Commission for this fill

        Returns:
            Tuple of (success, is_fully_filled)
        """
        child = self._orders.get(child_order_id)
        if not child:
            logger.warning("Child order not found for fill: %s", child_order_id)
            return False, False

        if child.status.is_terminal:
            logger.warning("Cannot fill terminal child order: %s status=%s", child_order_id, child.status)
            return False, False

        is_filled = child.apply_fill(fill_qty, fill_price, commission)

        logger.debug(
            "Child fill: %s qty=%.0f price=%.2f filled=%.0f/%.0f avg=%.4f",
            child_order_id,
            fill_qty,
            fill_price,
            child.filled_quantity,
            child.quantity,
            child.average_price,
        )
        return True, is_filled

    # ── Cancellation ───────────────────────────────────────────────

    async def cancel_child(self, child_order_id: str) -> bool:
        """Cancel a child order.

        Args:
            child_order_id: Child order identifier

        Returns:
            True if cancelled
        """
        child = self._orders.get(child_order_id)
        if not child:
            return False

        if child.status.is_terminal:
            return False

        child.status = ChildOrderStatus.CANCELLING
        success = await self.dispatcher.cancel(child)
        if success:
            child.status = ChildOrderStatus.CANCELLED

        return success

    async def cancel_all_for_parent(self, parent_order_id: str) -> int:
        """Cancel all active child orders for a parent.

        Args:
            parent_order_id: Parent order identifier

        Returns:
            Number of child orders cancelled
        """
        child_ids = self._by_parent.get(parent_order_id, [])
        cancelled = 0
        for child_id in child_ids:
            if await self.cancel_child(child_id):
                cancelled += 1
        return cancelled

    # ── Query API ──────────────────────────────────────────────────

    async def get_child(self, child_order_id: str) -> Optional[ChildOrder]:
        """Get a child order by ID.

        Args:
            child_order_id: Child order identifier

        Returns:
            ChildOrder or None
        """
        return self._orders.get(child_order_id)

    async def get_children_for_parent(self, parent_order_id: str) -> list[ChildOrder]:
        """Get all child orders for a parent.

        Args:
            parent_order_id: Parent order identifier

        Returns:
            List of child orders
        """
        child_ids = self._by_parent.get(parent_order_id, [])
        return [self._orders[cid] for cid in child_ids if cid in self._orders]

    async def get_active_children(self, parent_order_id: str) -> list[ChildOrder]:
        """Get active child orders for a parent.

        Args:
            parent_order_id: Parent order identifier

        Returns:
            List of active child orders
        """
        children = await self.get_children_for_parent(parent_order_id)
        return [c for c in children if c.status.is_active]

    async def get_fill_summary(self, parent_order_id: str) -> dict[str, Any]:
        """Get fill summary for a parent's children.

        Args:
            parent_order_id: Parent order identifier

        Returns:
            Fill summary dictionary
        """
        children = await self.get_children_for_parent(parent_order_id)
        total_qty = sum(c.quantity for c in children)
        filled_qty = sum(c.filled_quantity for c in children)
        total_notional = sum(c.filled_quantity * c.average_price for c in children if c.filled_quantity > 0)

        return {
            "parent_order_id": parent_order_id,
            "total_children": len(children),
            "filled_children": sum(1 for c in children if c.is_filled),
            "active_children": sum(1 for c in children if c.status.is_active),
            "total_quantity": total_qty,
            "filled_quantity": filled_qty,
            "fill_pct": filled_qty / total_qty if total_qty > 0 else 0.0,
            "average_price": total_notional / filled_qty if filled_qty > 0 else 0.0,
            "total_commission": sum(c.commission for c in children),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize manager state."""
        return {
            "total_children": len(self._orders),
            "active_children": sum(1 for c in self._orders.values() if c.status.is_active),
            "filled_children": sum(1 for c in self._orders.values() if c.is_filled),
            "parents": {pid: len(ids) for pid, ids in self._by_parent.items()},
        }
