"""Arrival Price Strategy — Arrival price benchmark execution.

Executes orders with the goal of matching or beating the arrival price
(the market price when the order was submitted). Uses a dynamic urgency
model that increases aggressiveness as time progresses.

Algorithm::

    Arrival Price → Track Deviation → Adjust Urgency → Child Orders

Parameters:
    - max_slippage_bps: Maximum allowed deviation from arrival price
    - urgency_profile: How urgency increases over time

Usage::

    strategy = ArrivalPriceStrategy()
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


class ArrivalPriceStrategy(ExecutionStrategy):
    """Arrival Price benchmark execution strategy.

    Aims to execute as close to the arrival price as possible.
    Uses a dynamic urgency model:
        - Early: Passive execution, prioritize price over speed
        - Mid: Balanced execution
        - Late: Aggressive execution, prioritize speed over price

    The urgency increases as the remaining time decreases, ensuring
    completion within the allocated duration.
    """

    def __init__(self) -> None:
        super().__init__()
        self._arrival_price: float = 0.0
        self._max_slippage_bps: float = 10.0
        self._total_qty: float = 0.0
        self._remaining_qty: float = 0.0
        self._current_slice: int = 0
        self._total_slices: int = 0
        self._started_at: Optional[datetime] = None
        self._duration: float = 0.0

    async def initialize(self, context: ExecutionContext) -> None:
        """Initialize Arrival Price strategy.

        Sets arrival price benchmark and urgency parameters.

        Args:
            context: Execution context
        """
        self.context = context
        self._arrival_price = context.price_limit or 0.0
        self._max_slippage_bps = context.max_slippage_bps
        self._total_qty = context.total_quantity
        self._remaining_qty = self._total_qty
        self._duration = context.effective_duration
        self._current_slice = 0
        self._started_at = datetime.now(timezone.utc)

        # Number of slices based on duration
        interval = context.slice_interval_seconds
        if interval <= 0:
            interval = 30.0  # More frequent for arrival price
        self._total_slices = max(1, int(self._duration / interval))

        logger.info(
            "Arrival Price initialized: arrival=%.2f max_slip=%.1f bps slices=%d qty=%.0f",
            self._arrival_price,
            self._max_slippage_bps,
            self._total_slices,
            self._total_qty,
        )

    async def next_child_order(self, metadata: ExecutionMetadata) -> Optional[ChildOrder]:
        """Produce the next Arrival Price child order.

        Order size increases as urgency increases (time progresses).

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

        if self._current_slice >= self._total_slices:
            self._is_complete = True
            return None

        # Calculate urgency (0-1): how far through the schedule we are
        if self._total_slices > 0:
            urgency = self._current_slice / self._total_slices
        else:
            urgency = 1.0

        # Urgency affects slice size: more aggressive = larger slices
        # Linear interpolation from 0.5x to 2x base size
        base_size = self._remaining_qty / max(1, self._total_slices - self._current_slice)
        urgency_multiplier = 0.5 + urgency * 1.5  # 0.5 → 2.0
        slice_qty = base_size * urgency_multiplier

        # Apply constraints
        slice_qty = min(slice_qty, self._remaining_qty)
        slice_qty = max(slice_qty, self.context.min_slice_quantity)

        if self.context.max_slice_quantity > 0:
            slice_qty = min(slice_qty, self.context.max_slice_quantity)

        slice_qty = math.floor(slice_qty * 100) / 100

        if slice_qty <= 0:
            self._current_slice += 1
            return None

        # Use limit price to control slippage
        price = 0.0
        if self._arrival_price > 0 and self._max_slippage_bps > 0:
            slippage = self._arrival_price * self._max_slippage_bps / 10000
            side = getattr(self.context.parent_order, "side", "")
            if str(side).upper() == "BUY":
                price = self._arrival_price + slippage  # Max price for buy
            else:
                price = self._arrival_price - slippage  # Min price for sell

        parent_order_id = self.context.parent_order.order_id if hasattr(self.context.parent_order, "order_id") else ""
        child = self._create_child_order(
            parent_order_id=parent_order_id,
            quantity=slice_qty,
            price=price,
            slice_index=self._current_slice,
        )
        child.order_type = "LIMIT" if price > 0 else "MARKET"

        self._remaining_qty -= slice_qty
        self._current_slice += 1

        logger.debug(
            "Arrival Price slice %d/%d: qty=%.2f urgency=%.1f%% price=%.2f",
            self._current_slice,
            self._total_slices,
            slice_qty,
            urgency * 100,
            price,
        )

        return child

    async def update(self, metadata: ExecutionMetadata) -> None:
        """Update Arrival Price state.

        Adjusts remaining quantity and checks slippage vs arrival.

        Args:
            metadata: Current execution metadata
        """
        self._remaining_qty = metadata.remaining_quantity

        # Check slippage vs arrival
        if self._arrival_price > 0 and metadata.average_price > 0:
            slippage = abs(metadata.average_price - self._arrival_price) / self._arrival_price * 10000
            if slippage > self._max_slippage_bps:
                logger.warning(
                    "Arrival Price slippage exceeded: %.1f bps > %.1f bps limit",
                    slippage,
                    self._max_slippage_bps,
                )

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
        """Complete the Arrival Price strategy."""
        self._is_complete = True
        logger.info(
            "Arrival Price strategy completed: slices=%d/%d",
            self._current_slice,
            self._total_slices,
        )
