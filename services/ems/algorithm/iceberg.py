"""Iceberg Strategy — Hidden quantity execution.

Executes large orders by displaying only a small visible portion
to the market, hiding the true order size to minimize market impact.
When the visible portion fills, a new slice is automatically dispatched.

Algorithm::

    Large Order → Visible Portion → Fill → Refresh Visible → Repeat

Parameters:
    - visible_quantity: Displayed quantity per slice
    - refresh_quantity: Quantity to refresh when visible portion fills

Usage::

    strategy = IcebergStrategy()
    await strategy.initialize(context)
    child = await strategy.next_child_order(metadata)
"""

from __future__ import annotations

import logging
import math
from typing import Optional

from services.ems.algorithm.execution_strategy import ExecutionStrategy
from services.ems.child_order import ChildOrder
from services.ems.execution_context import ExecutionContext
from services.ems.execution_metadata import ExecutionMetadata

logger = logging.getLogger(__name__)


class IcebergStrategy(ExecutionStrategy):
    """Iceberg / Reserve order execution strategy.

    Shows only a small visible portion of the total order to the market
    to avoid revealing the full order size. Automatically refreshes
    the visible quantity when the current slice is filled.

    Benefits:
        - Minimizes market impact of large orders
        - Hides true order size from other market participants
        - Reduces adverse selection
    """

    def __init__(self) -> None:
        super().__init__()
        self._visible_qty: float = 0.0
        self._refresh_qty: float = 0.0
        self._remaining_qty: float = 0.0
        self._current_slice: int = 0
        self._active_children: int = 0
        self._max_active_children: int = 1  # Typically 1 visible slice at a time

    async def initialize(self, context: ExecutionContext) -> None:
        """Initialize Iceberg strategy.

        Sets visible quantity and refresh parameters.

        Args:
            context: Execution context
        """
        self.context = context

        total_qty = context.total_quantity

        # Visible quantity: user-specified or default to 10% of total
        if context.visible_quantity > 0:
            self._visible_qty = context.visible_quantity
        else:
            self._visible_qty = max(1.0, total_qty * 0.10)

        self._refresh_qty = context.strategy_params.get("refresh_quantity", self._visible_qty)
        self._remaining_qty = total_qty
        self._current_slice = 0
        self._max_active_children = context.strategy_params.get("max_active_children", 1)

        logger.info(
            "Iceberg initialized: visible=%.0f refresh=%.0f total=%.0f max_active=%d",
            self._visible_qty,
            self._refresh_qty,
            total_qty,
            self._max_active_children,
        )

    async def next_child_order(self, metadata: ExecutionMetadata) -> Optional[ChildOrder]:
        """Produce the next Iceberg slice.

        Dispatches a new visible slice only when active children
        are below the maximum.

        Args:
            metadata: Current execution metadata

        Returns:
            ChildOrder or None
        """
        if self._is_paused or self._is_complete:
            return None

        if self._remaining_qty <= 0:
            self._is_complete = True
            return None

        # Check if we can dispatch more
        if self._active_children >= self._max_active_children:
            return None

        # Calculate slice quantity
        slice_qty = min(self._visible_qty, self._remaining_qty)

        if self.context.max_slice_quantity > 0:
            slice_qty = min(slice_qty, self.context.max_slice_quantity)
        slice_qty = max(slice_qty, self.context.min_slice_quantity)

        slice_qty = math.floor(slice_qty * 100) / 100

        if slice_qty <= 0:
            return None

        # Create child order with limit price to avoid slippage
        price = 0.0
        if self.context.price_limit:
            price = self.context.price_limit

        parent_order_id = self.context.parent_order.order_id if hasattr(self.context.parent_order, "order_id") else ""
        child = self._create_child_order(
            parent_order_id=parent_order_id,
            quantity=slice_qty,
            price=price,
            slice_index=self._current_slice,
        )
        child.order_type = "LIMIT" if price > 0 else "MARKET"

        self._remaining_qty -= slice_qty
        self._active_children += 1
        self._current_slice += 1

        logger.debug(
            "Iceberg slice %d: visible=%.0f remaining=%.0f active=%d",
            self._current_slice,
            slice_qty,
            self._remaining_qty,
            self._active_children,
        )

        return child

    async def update(self, metadata: ExecutionMetadata) -> None:
        """Update Iceberg state with latest metadata.

        Args:
            metadata: Current execution metadata
        """
        self._remaining_qty = metadata.remaining_quantity

    async def on_fill(self, child: ChildOrder, metadata: ExecutionMetadata) -> None:
        """Handle a child order fill event.

        When a slice is filled, decrement active children count so
        a new slice can be dispatched.

        Args:
            child: Child order that received a fill
            metadata: Current execution metadata
        """
        self._remaining_qty = metadata.remaining_quantity

        if child.is_filled:
            self._active_children = max(0, self._active_children - 1)

        if self._remaining_qty <= 0:
            self._is_complete = True
            logger.info("Iceberg target quantity reached")

    async def complete(self) -> None:
        """Complete the Iceberg strategy."""
        self._is_complete = True
        logger.info(
            "Iceberg strategy completed: slices=%d remaining=%.0f",
            self._current_slice,
            self._remaining_qty,
        )
