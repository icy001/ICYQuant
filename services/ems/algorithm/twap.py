"""TWAP Strategy — Time-Weighted Average Price execution.

Splits the parent order into equal time slices and dispatches child
orders at regular intervals. The simplest and most common institutional
execution algorithm.

Algorithm::

    Parent Order → Divide into N time slices → Dispatch equal qty each interval

Parameters:
    - duration_seconds: Total execution duration
    - slice_count: Number of slices (auto-computed if not specified)

Usage::

    strategy = TWAPStrategy()
    await strategy.initialize(context)
    child = await strategy.next_child_order(metadata)
"""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Optional

from services.ems.algorithm.execution_strategy import ExecutionStrategy
from services.ems.child_order import ChildOrder
from services.ems.execution_context import ExecutionContext
from services.ems.execution_metadata import ExecutionMetadata

logger = logging.getLogger(__name__)


class TWAPStrategy(ExecutionStrategy):
    """Time-Weighted Average Price execution strategy.

    Splits the parent order into equal time intervals and dispatches
    equal-sized child orders at each interval.

    The strategy calculates:
        - Number of slices based on duration and interval
        - Equal quantity per slice
        - Schedule timing for each slice
    """

    def __init__(self) -> None:
        super().__init__()
        self._total_slices: int = 0
        self._current_slice: int = 0
        self._slice_quantity: float = 0.0
        self._remaining_qty: float = 0.0
        self._started_at: Optional[datetime] = None

    async def initialize(self, context: ExecutionContext) -> None:
        """Initialize TWAP slicing schedule.

        Calculates the number of slices and quantity per slice based
        on the execution duration and slice interval.

        Args:
            context: Execution context
        """
        self.context = context

        # Determine number of slices
        if context.slice_count > 0:
            self._total_slices = context.slice_count
        else:
            # Default: slice every 60 seconds
            interval = context.slice_interval_seconds
            if interval <= 0:
                interval = 60.0
            self._total_slices = max(1, int(context.effective_duration / interval))

        # Calculate quantity per slice
        total_qty = context.total_quantity
        self._slice_quantity = total_qty / self._total_slices
        self._remaining_qty = total_qty
        self._current_slice = 0
        self._started_at = datetime.now(timezone.utc)

        logger.info(
            "TWAP initialized: slices=%d qty_per_slice=%.2f total_qty=%.0f duration=%.0fs",
            self._total_slices,
            self._slice_quantity,
            total_qty,
            context.effective_duration,
        )

    async def next_child_order(self, metadata: ExecutionMetadata) -> Optional[ChildOrder]:
        """Produce the next TWAP child order.

        Returns a child order for the current slice if the schedule
        indicates it's time. Returns None if paused or complete.

        Args:
            metadata: Current execution metadata

        Returns:
            ChildOrder or None
        """
        if self._is_paused or self._is_complete:
            return None

        # Check if all slices dispatched
        if self._current_slice >= self._total_slices:
            self._is_complete = True
            logger.info("TWAP complete: all %d slices dispatched", self._total_slices)
            return None

        # Check if remaining quantity is negligible
        if self._remaining_qty <= 0:
            self._is_complete = True
            return None

        # Calculate quantity for this slice (handle remainder)
        slice_qty = min(self._slice_quantity, self._remaining_qty)

        if slice_qty < self.context.min_slice_quantity:
            # Add to next slice
            self._current_slice += 1
            return None

        # Enforce max slice quantity
        if self.context.max_slice_quantity > 0:
            slice_qty = min(slice_qty, self.context.max_slice_quantity)

        # Round to reasonable precision
        slice_qty = math.floor(slice_qty * 100) / 100

        if slice_qty <= 0:
            self._is_complete = True
            return None

        # Create child order
        parent_order_id = self.context.parent_order.order_id if hasattr(self.context.parent_order, "order_id") else ""
        child = self._create_child_order(
            parent_order_id=parent_order_id,
            quantity=slice_qty,
            price=0.0,  # Market order for TWAP
            slice_index=self._current_slice,
        )

        self._remaining_qty -= slice_qty
        self._current_slice += 1

        logger.debug(
            "TWAP slice %d/%d: qty=%.2f remaining=%.2f",
            self._current_slice,
            self._total_slices,
            slice_qty,
            self._remaining_qty,
        )

        return child

    async def update(self, metadata: ExecutionMetadata) -> None:
        """Update TWAP state with latest metadata.

        Adjusts remaining quantity based on fill progress.

        Args:
            metadata: Current execution metadata
        """
        self._remaining_qty = metadata.remaining_quantity

    async def on_fill(self, child: ChildOrder, metadata: ExecutionMetadata) -> None:
        """Handle a child order fill event.

        Args:
            child: Child order that received a fill
            metadata: Current execution metadata
        """
        self._remaining_qty = metadata.remaining_quantity

        if self._remaining_qty <= 0:
            self._is_complete = True
            logger.info("TWAP target quantity reached")

    async def complete(self) -> None:
        """Complete the TWAP strategy."""
        self._is_complete = True
        logger.info(
            "TWAP strategy completed: slices=%d/%d",
            self._current_slice,
            self._total_slices,
        )
