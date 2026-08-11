"""POV Strategy — Percentage of Volume execution.

Maintains a fixed participation rate of market volume. Child orders
are sized dynamically based on recent market volume to maintain the
target participation rate.

Algorithm::

    Market Volume → Participation Rate → Dynamic Child Order Size → Dispatch

Parameters:
    - participation_rate: Target participation rate (0-1)
    - lookback_seconds: Lookback window for volume estimation

Usage::

    strategy = POVStrategy()
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


class POVStrategy(ExecutionStrategy):
    """Percentage of Volume execution strategy.

    Maintains a constant participation rate of total market volume.
    Child order sizes are dynamically adjusted based on observed
    market volume to keep the target participation rate.

    Key feature: Adapts to market conditions — larger child orders
    during high volume periods, smaller during low volume.
    """

    def __init__(self) -> None:
        super().__init__()
        self._participation_rate: float = 0.05
        self._lookback_seconds: float = 60.0
        self._estimated_market_volume: float = 0.0
        self._remaining_qty: float = 0.0
        self._current_slice: int = 0
        self._max_slices: int = 0

    async def initialize(self, context: ExecutionContext) -> None:
        """Initialize POV strategy.

        Sets participation rate from context and computes max slices.

        Args:
            context: Execution context
        """
        self.context = context
        self._participation_rate = context.participation_rate
        self._lookback_seconds = context.strategy_params.get("lookback_seconds", 60.0)

        total_qty = context.total_quantity
        self._remaining_qty = total_qty
        self._current_slice = 0

        # Max slices based on duration and min interval
        interval = context.slice_interval_seconds
        if interval <= 0:
            interval = 60.0
        self._max_slices = max(1, int(context.effective_duration / interval))

        # Initial volume estimate
        self._estimated_market_volume = context.strategy_params.get(
            "initial_volume_estimate", total_qty * 10
        )

        logger.info(
            "POV initialized: participation=%.1f%% max_slices=%d total_qty=%.0f",
            self._participation_rate * 100,
            self._max_slices,
            total_qty,
        )

    async def next_child_order(self, metadata: ExecutionMetadata) -> Optional[ChildOrder]:
        """Produce the next POV child order.

        Size is calculated as participation_rate * estimated_market_volume.

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

        # Update volume estimate based on fill rate
        fill_rate = metadata.fill_rate_per_minute
        if fill_rate > 0 and self._participation_rate > 0:
            estimated_total = fill_rate / self._participation_rate
            # Exponential smoothing
            alpha = 0.3
            self._estimated_market_volume = (
                alpha * estimated_total + (1 - alpha) * self._estimated_market_volume
            )

        # Calculate child order size
        slice_qty = self._estimated_market_volume * self._participation_rate

        # Apply constraints
        slice_qty = min(slice_qty, self._remaining_qty)
        slice_qty = max(slice_qty, self.context.min_slice_quantity)

        if self.context.max_slice_quantity > 0:
            slice_qty = min(slice_qty, self.context.max_slice_quantity)

        slice_qty = math.floor(slice_qty * 100) / 100

        if slice_qty <= 0:
            return None

        parent_order_id = self.context.parent_order.order_id if hasattr(self.context.parent_order, "order_id") else ""
        child = self._create_child_order(
            parent_order_id=parent_order_id,
            quantity=slice_qty,
            price=0.0,
            slice_index=self._current_slice,
        )

        self._remaining_qty -= slice_qty
        self._current_slice += 1

        logger.debug(
            "POV slice %d: qty=%.2f est_vol=%.0f part=%.1f%% remaining=%.0f",
            self._current_slice,
            slice_qty,
            self._estimated_market_volume,
            self._participation_rate * 100,
            self._remaining_qty,
        )

        return child

    async def update(self, metadata: ExecutionMetadata) -> None:
        """Update POV state with latest metadata.

        Args:
            metadata: Current execution metadata
        """
        self._remaining_qty = metadata.remaining_quantity

        # Update volume estimate from fill data
        elapsed = metadata.duration_seconds
        if elapsed > 0 and metadata.filled_quantity > 0:
            fill_rate = metadata.filled_quantity / elapsed * 60
            if self._participation_rate > 0:
                self._estimated_market_volume = fill_rate / self._participation_rate

    async def on_fill(self, child: ChildOrder, metadata: ExecutionMetadata) -> None:
        """Handle a child order fill event.

        Args:
            child: Child order that received a fill
            metadata: Current execution metadata
        """
        self._remaining_qty = metadata.remaining_quantity
        if self._remaining_qty <= 0:
            self._is_complete = True

    async def complete(self) -> None:
        """Complete the POV strategy."""
        self._is_complete = True
        logger.info(
            "POV strategy completed: slices=%d participation=%.1f%%",
            self._current_slice,
            self._participation_rate * 100,
        )
