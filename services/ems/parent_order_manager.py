"""Parent Order Manager — Parent order lifecycle management.

Manages the full lifecycle of parent orders within the EMS, including
creation, status tracking, child order aggregation, and reporting.

Responsibilities:
    - Parent order registration and lifecycle
    - Child order aggregation and progress tracking
    - Fill aggregation from child orders
    - Parent-level status management

Usage::

    manager = ParentOrderManager()
    parent = await manager.create(order, strategy="TWAP")
    await manager.update_status(parent.parent_order_id, ParentOrderStatus.ACTIVE)
    await manager.get_progress(parent.parent_order_id)
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from services.ems.child_order import ChildOrder
from services.ems.parent_order import ParentOrder, ParentOrderStatus
from services.oms.order.models import Order

logger = logging.getLogger(__name__)


class ParentOrderManager:
    """Manages parent order lifecycle and aggregation.

    Tracks all parent orders, their child orders, and aggregate execution
    state. Provides query and reporting capabilities.

    Attributes:
        _orders: Map of parent_order_id → ParentOrder
        _child_orders: Map of parent_order_id → list[ChildOrder]
    """

    def __init__(self) -> None:
        self._orders: dict[str, ParentOrder] = {}
        self._child_orders: dict[str, list[ChildOrder]] = {}

    # ── Creation ───────────────────────────────────────────────────

    async def create(
        self,
        oms_order: Order,
        strategy: str = "TWAP",
        venue: str = "",
        benchmark_price: float = 0.0,
        **kwargs: Any,
    ) -> ParentOrder:
        """Create a parent order from an OMS order.

        Args:
            oms_order: OMS order to execute
            strategy: Execution algorithm
            venue: Target venue
            benchmark_price: Arrival price benchmark
            **kwargs: Additional metadata

        Returns:
            Created ParentOrder
        """
        parent = ParentOrder(
            oms_order_id=oms_order.order_id if hasattr(oms_order, "order_id") else "",
            symbol=getattr(oms_order, "symbol", ""),
            side=getattr(oms_order, "side", ""),
            quantity=getattr(oms_order, "quantity", 0.0),
            remaining_quantity=getattr(oms_order, "quantity", 0.0),
            strategy=strategy,
            venue=venue,
            benchmark_price=benchmark_price,
            metadata=kwargs,
        )
        self._orders[parent.parent_order_id] = parent
        self._child_orders[parent.parent_order_id] = []

        logger.info(
            "Parent order created: %s symbol=%s qty=%.0f strategy=%s",
            parent.parent_order_id,
            parent.symbol,
            parent.quantity,
            strategy,
        )
        return parent

    # ── Status Management ──────────────────────────────────────────

    async def update_status(self, parent_order_id: str, status: ParentOrderStatus) -> bool:
        """Update parent order status.

        Args:
            parent_order_id: Parent order identifier
            status: New status

        Returns:
            True if updated
        """
        parent = self._orders.get(parent_order_id)
        if not parent:
            logger.warning("Parent order not found: %s", parent_order_id)
            return False

        parent.status = status
        if status == ParentOrderStatus.ACTIVE and not parent.started_at:
            parent.start()
        elif status == ParentOrderStatus.COMPLETED:
            parent.complete()
        elif status == ParentOrderStatus.CANCELLED:
            parent.cancel()

        logger.debug("Parent order status: %s → %s", parent_order_id, status.value)
        return True

    # ── Child Order Aggregation ────────────────────────────────────

    async def add_child_order(self, parent_order_id: str, child: ChildOrder) -> bool:
        """Register a child order with its parent.

        Args:
            parent_order_id: Parent order identifier
            child: Child order

        Returns:
            True if added
        """
        parent = self._orders.get(parent_order_id)
        if not parent:
            logger.warning("Parent order not found for child: %s", parent_order_id)
            return False

        parent.add_child(child.order_id)
        self._child_orders[parent_order_id].append(child)
        return True

    async def on_child_fill(
        self, parent_order_id: str, child: ChildOrder, fill_qty: float, fill_price: float
    ) -> None:
        """Handle a child order fill, aggregating to parent.

        Args:
            parent_order_id: Parent order identifier
            child: Child order that received a fill
            fill_qty: Fill quantity
            fill_price: Fill price
        """
        parent = self._orders.get(parent_order_id)
        if not parent:
            return

        parent.apply_fill(fill_qty, fill_price, child.commission or 0.0)

        if child.is_filled:
            parent.child_filled(child.order_id)

        # Check if parent is complete
        if parent.fill_pct >= 0.999 or parent.remaining_quantity <= 0:
            await self.update_status(parent_order_id, ParentOrderStatus.COMPLETED)

    async def on_child_cancelled(self, parent_order_id: str, child_order_id: str) -> None:
        """Handle a child order cancellation.

        Args:
            parent_order_id: Parent order identifier
            child_order_id: Cancelled child order ID
        """
        parent = self._orders.get(parent_order_id)
        if parent:
            parent.child_cancelled(child_order_id)

    # ── Query API ──────────────────────────────────────────────────

    async def get_parent(self, parent_order_id: str) -> Optional[ParentOrder]:
        """Get a parent order by ID.

        Args:
            parent_order_id: Parent order identifier

        Returns:
            ParentOrder or None
        """
        return self._orders.get(parent_order_id)

    async def get_child_orders(self, parent_order_id: str) -> list[ChildOrder]:
        """Get all child orders for a parent.

        Args:
            parent_order_id: Parent order identifier

        Returns:
            List of child orders
        """
        return self._child_orders.get(parent_order_id, [])

    async def get_progress(self, parent_order_id: str) -> dict[str, Any]:
        """Get execution progress for a parent order.

        Args:
            parent_order_id: Parent order identifier

        Returns:
            Progress summary dictionary
        """
        parent = self._orders.get(parent_order_id)
        if not parent:
            return {}

        children = self._child_orders.get(parent_order_id, [])

        return {
            "parent_order_id": parent.parent_order_id,
            "status": parent.status.value,
            "fill_pct": parent.fill_pct,
            "filled_quantity": parent.filled_quantity,
            "remaining_quantity": parent.remaining_quantity,
            "average_price": parent.average_price,
            "slippage_bps": parent.slippage_bps,
            "total_children": len(children),
            "active_children": parent.active_children,
            "filled_children": parent.filled_children,
            "duration_seconds": parent.duration_seconds,
        }

    async def get_all_parents(self) -> list[ParentOrder]:
        """Get all parent orders.

        Returns:
            List of all parent orders
        """
        return list(self._orders.values())

    async def get_active_parents(self) -> list[ParentOrder]:
        """Get all active parent orders.

        Returns:
            List of active parent orders
        """
        return [p for p in self._orders.values() if p.status.is_active]

    # ── Cleanup ────────────────────────────────────────────────────

    async def remove(self, parent_order_id: str) -> bool:
        """Remove a parent order and its children.

        Args:
            parent_order_id: Parent order identifier

        Returns:
            True if removed
        """
        self._orders.pop(parent_order_id, None)
        self._child_orders.pop(parent_order_id, None)
        return True

    def to_dict(self) -> dict[str, Any]:
        """Serialize manager state."""
        return {
            "total_parents": len(self._orders),
            "active_parents": len([p for p in self._orders.values() if p.status.is_active]),
            "total_children": sum(len(v) for v in self._child_orders.values()),
        }
