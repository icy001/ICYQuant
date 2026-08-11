"""Algorithm Execution Framework — Strategy abstraction and lifecycle.

Defines the base ExecutionStrategy interface that all execution algorithms
must implement. Provides a uniform lifecycle and extension points.

Lifecycle::

    initialize() → next_child_order() → update() → on_fill() → complete()

Usage::

    class MyStrategy(ExecutionStrategy):
        async def initialize(self, context):
            self.context = context

        async def next_child_order(self, metadata):
            return ChildOrder(...)

        async def update(self, metadata):
            pass

        async def on_fill(self, child, metadata):
            pass

        async def complete(self):
            pass
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from typing import Any, Optional

from services.ems.child_order import ChildOrder
from services.ems.execution_context import ExecutionContext
from services.ems.execution_metadata import ExecutionMetadata

logger = logging.getLogger(__name__)


class ExecutionStrategy(ABC):
    """Abstract base class for execution algorithms.

    All execution algorithms follow this unified lifecycle:
    1. initialize() — Setup with execution context
    2. next_child_order() — Produce child orders on schedule
    3. update() — React to market/meta updates
    4. on_fill() — Process fill events
    5. complete() — Cleanup and finalize

    Attributes:
        context: Execution context with order and parameters
        _is_paused: Whether the strategy is paused
        _is_complete: Whether the strategy has completed
    """

    def __init__(self) -> None:
        self.context: Optional[ExecutionContext] = None
        self._is_paused = False
        self._is_complete = False

    @property
    def name(self) -> str:
        """Strategy name for registration."""
        return self.__class__.__name__.upper()

    @property
    def is_paused(self) -> bool:
        """Whether the strategy is currently paused."""
        return self._is_paused

    @property
    def is_complete(self) -> bool:
        """Whether the strategy has completed."""
        return self._is_complete

    # ── Lifecycle Methods ──────────────────────────────────────────

    @abstractmethod
    async def initialize(self, context: ExecutionContext) -> None:
        """Initialize the strategy with execution context.

        Called once before execution begins. Set up parameters,
        compute slicing schedule, etc.

        Args:
            context: Execution context with order and parameters
        """
        ...

    @abstractmethod
    async def next_child_order(self, metadata: ExecutionMetadata) -> Optional[ChildOrder]:
        """Produce the next child order to dispatch.

        Called on each schedule tick. Returns a child order if one
        should be dispatched, or None if waiting or done.

        Args:
            metadata: Current execution metadata

        Returns:
            ChildOrder to dispatch, or None if no order ready
        """
        ...

    @abstractmethod
    async def update(self, metadata: ExecutionMetadata) -> None:
        """Update strategy state with latest metadata.

        Called periodically to allow the strategy to adapt to
        changing market conditions.

        Args:
            metadata: Current execution metadata
        """
        ...

    @abstractmethod
    async def on_fill(self, child: ChildOrder, metadata: ExecutionMetadata) -> None:
        """Handle a child order fill event.

        Called when a dispatched child order receives a fill.
        The strategy can adjust future slices based on fills.

        Args:
            child: Child order that received a fill
            metadata: Current execution metadata
        """
        ...

    @abstractmethod
    async def complete(self) -> None:
        """Complete the strategy and clean up resources.

        Called when execution is finished or terminated.
        """
        ...

    # ── Control Methods ────────────────────────────────────────────

    async def pause(self) -> None:
        """Pause the strategy.

        Stops producing new child orders. Existing orders continue.
        """
        self._is_paused = True
        logger.debug("Strategy paused: %s", self.name)

    async def resume(self) -> None:
        """Resume the strategy.

        Continues producing child orders.
        """
        self._is_paused = False
        logger.debug("Strategy resumed: %s", self.name)

    # ── Helper Methods ─────────────────────────────────────────────

    def _create_child_order(
        self,
        parent_order_id: str,
        quantity: float,
        price: float = 0.0,
        slice_index: int = 0,
    ) -> ChildOrder:
        """Create a child order with context-derived attributes.

        Args:
            parent_order_id: Parent order identifier
            quantity: Order quantity
            price: Limit price (0 for market)
            slice_index: Position in slice sequence

        Returns:
            ChildOrder instance
        """
        ctx = self.context
        return ChildOrder(
            parent_order_id=parent_order_id,
            symbol=ctx.parent_order.symbol if hasattr(ctx.parent_order, "symbol") else "",
            side=ctx.parent_order.side if hasattr(ctx.parent_order, "side") else "",
            quantity=quantity,
            remaining_quantity=quantity,
            price=price,
            venue=ctx.venue,
            slice_index=slice_index,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serialize strategy state."""
        return {
            "name": self.name,
            "is_paused": self._is_paused,
            "is_complete": self._is_complete,
        }
