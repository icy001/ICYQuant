"""Order Splitter — Intelligent multi-venue order splitting.

Splits large parent orders into optimally-sized child orders across
multiple venues, considering liquidity, market impact, and venue
constraints.

Splitting Strategy::

    Parent Order → Venue Allocation → Child Orders → Parallel Dispatch

Usage::

    splitter = OrderSplitter()
    splits = await splitter.split(order, venues, liquidity)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import Any, Optional

from services.execution_gateway.venue_registry import Venue

logger = logging.getLogger(__name__)


@dataclass
class OrderSplit:
    """A single split allocation to a venue.

    Attributes:
        venue: Target venue name
        quantity: Allocated quantity
        fraction: Fraction of total order
        priority: Execution priority (1 = highest)
        reason: Allocation rationale
    """

    venue: str = ""
    quantity: float = 0.0
    fraction: float = 0.0
    priority: int = 1
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "venue": self.venue,
            "quantity": self.quantity,
            "fraction": self.fraction,
            "priority": self.priority,
            "reason": self.reason,
        }


@dataclass
class SplitPlan:
    """Complete order split plan.

    Attributes:
        order_id: Parent order identifier
        total_quantity: Total order quantity
        splits: Individual venue allocations
        remaining_quantity: Unallocated quantity
        strategy: Splitting strategy name
    """

    order_id: str = ""
    total_quantity: float = 0.0
    splits: list[OrderSplit] = field(default_factory=list)
    remaining_quantity: float = 0.0
    strategy: str = "proportional"

    @property
    def split_count(self) -> int:
        return len(self.splits)

    @property
    def is_fully_allocated(self) -> bool:
        return abs(self.remaining_quantity) < 0.0001

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "total_quantity": self.total_quantity,
            "split_count": self.split_count,
            "remaining_quantity": self.remaining_quantity,
            "is_fully_allocated": self.is_fully_allocated,
            "strategy": self.strategy,
            "splits": [s.to_dict() for s in self.splits],
        }


class OrderSplitter:
    """Intelligent order splitter for multi-venue execution.

    Splits orders based on venue liquidity, market impact minimization,
    and execution constraints.

    Attributes:
        _max_splits: Maximum number of venue splits
        _min_split_pct: Minimum split as fraction of total
        _liquidity_weight: Weight for liquidity-based allocation
    """

    def __init__(
        self,
        max_splits: int = 5,
        min_split_pct: float = 0.05,
    ) -> None:
        self._max_splits = max_splits
        self._min_split_pct = min_split_pct

    # ── Splitting ──────────────────────────────────────────────────

    async def split(
        self,
        order_id: str,
        total_quantity: float,
        venues: list[Venue],
        liquidity_scores: Optional[dict[str, dict[str, Any]]] = None,
        strategy: str = "proportional",
    ) -> SplitPlan:
        """Split an order across venues.

        Args:
            order_id: Parent order identifier
            total_quantity: Total order quantity
            venues: Available venues
            liquidity_scores: Liquidity analysis per venue
            strategy: Splitting strategy (proportional, equal, depth-based)

        Returns:
            SplitPlan with venue allocations
        """
        if not venues:
            logger.warning("No venues for splitting order %s", order_id)
            return SplitPlan(
                order_id=order_id,
                total_quantity=total_quantity,
                remaining_quantity=total_quantity,
                strategy=strategy,
            )

        if strategy == "equal":
            splits = self._equal_split(order_id, total_quantity, venues)
        elif strategy == "depth-based":
            splits = self._depth_based_split(
                order_id, total_quantity, venues, liquidity_scores or {}
            )
        else:
            splits = self._proportional_split(
                order_id, total_quantity, venues, liquidity_scores or {}
            )

        # Calculate remaining
        allocated = sum(s.quantity for s in splits)
        remaining = total_quantity - allocated

        return SplitPlan(
            order_id=order_id,
            total_quantity=total_quantity,
            splits=splits,
            remaining_quantity=max(0.0, remaining),
            strategy=strategy,
        )

    async def determine_splits(
        self,
        quantity: float,
        venue: Any,
        liquidity_scores: Optional[dict[str, dict[str, Any]]] = None,
    ) -> int:
        """Determine optimal number of child orders.

        Args:
            quantity: Order quantity
            venue: Selected venue
            liquidity_scores: Liquidity analysis

        Returns:
            Recommended number of child orders
        """
        if quantity <= 0:
            return 1

        # Simple heuristic based on size relative to liquidity
        liquidity = (liquidity_scores or {}).get(venue.name if hasattr(venue, 'name') else str(venue), {})
        depth = liquidity.get("depth_bps", 50.0)

        if depth <= 0:
            return 1

        ratio = quantity / depth

        if ratio <= 0.1:
            return 1
        elif ratio <= 0.5:
            return 2
        elif ratio <= 1.0:
            return 3
        elif ratio <= 2.0:
            return 5
        else:
            return min(10, math.ceil(ratio))

    # ── Split Strategies ───────────────────────────────────────────

    def _proportional_split(
        self,
        order_id: str,
        total_quantity: float,
        venues: list[Venue],
        liquidity_scores: dict[str, dict[str, Any]],
    ) -> list[OrderSplit]:
        """Split proportionally to venue liquidity scores.

        Args:
            order_id: Order identifier
            total_quantity: Total quantity
            venues: Available venues
            liquidity_scores: Liquidity analysis

        Returns:
            List of OrderSplit objects
        """
        # Get liquidity scores
        scores = {}
        for venue in venues:
            score = liquidity_scores.get(venue.name, {}).get("score", venue.liquidity_score)
            scores[venue.name] = max(score, 0.01)

        total_score = sum(scores.values())
        if total_score <= 0:
            return []

        splits: list[OrderSplit] = []
        remaining = total_quantity

        sorted_venues = sorted(venues, key=lambda v: scores.get(v.name, 0), reverse=True)
        active_venues = sorted_venues[:self._max_splits]

        for i, venue in enumerate(active_venues):
            if i == len(active_venues) - 1:
                # Last venue gets remainder
                qty = remaining
            else:
                fraction = scores[venue.name] / total_score
                qty = total_quantity * fraction

                # Apply minimum split
                if qty < total_quantity * self._min_split_pct:
                    qty = total_quantity * self._min_split_pct

                qty = min(qty, remaining)

            if qty > 0:
                splits.append(OrderSplit(
                    venue=venue.name,
                    quantity=qty,
                    fraction=qty / total_quantity if total_quantity > 0 else 0,
                    priority=i + 1,
                    reason=f"Proportional: score={scores[venue.name]:.2f}",
                ))
                remaining -= qty

        return splits

    def _equal_split(
        self,
        order_id: str,
        total_quantity: float,
        venues: list[Venue],
    ) -> list[OrderSplit]:
        """Split equally across venues.

        Args:
            order_id: Order identifier
            total_quantity: Total quantity
            venues: Available venues

        Returns:
            List of OrderSplit objects
        """
        active = venues[:self._max_splits]
        if not active:
            return []

        per_venue = total_quantity / len(active)

        splits: list[OrderSplit] = []
        remaining = total_quantity

        for i, venue in enumerate(active):
            qty = remaining if i == len(active) - 1 else per_venue
            if qty > 0:
                splits.append(OrderSplit(
                    venue=venue.name,
                    quantity=qty,
                    fraction=1.0 / len(active),
                    priority=i + 1,
                    reason="Equal allocation",
                ))
                remaining -= qty

        return splits

    def _depth_based_split(
        self,
        order_id: str,
        total_quantity: float,
        venues: list[Venue],
        liquidity_scores: dict[str, dict[str, Any]],
    ) -> list[OrderSplit]:
        """Split based on available depth at each venue.

        Args:
            order_id: Order identifier
            total_quantity: Total quantity
            venues: Available venues
            liquidity_scores: Liquidity analysis

        Returns:
            List of OrderSplit objects
        """
        depths = {}
        for venue in venues:
            depth = liquidity_scores.get(venue.name, {}).get("depth_bps", 50.0)
            depths[venue.name] = max(depth, 1.0)

        total_depth = sum(depths.values())
        if total_depth <= 0:
            return []

        splits: list[OrderSplit] = []
        remaining = total_quantity

        sorted_venues = sorted(venues, key=lambda v: depths.get(v.name, 0), reverse=True)
        active = sorted_venues[:self._max_splits]

        for i, venue in enumerate(active):
            capacity = depths[venue.name]
            if i == len(active) - 1:
                qty = remaining
            else:
                qty = min(capacity * 0.5, remaining)
                qty = max(qty, total_quantity * self._min_split_pct)

            qty = min(qty, remaining)
            if qty > 0:
                splits.append(OrderSplit(
                    venue=venue.name,
                    quantity=qty,
                    fraction=qty / total_quantity if total_quantity > 0 else 0,
                    priority=i + 1,
                    reason=f"Depth-based: depth={depths[venue.name]:.1f}",
                ))
                remaining -= qty

        return splits

    def to_dict(self) -> dict[str, Any]:
        """Serialize splitter state."""
        return {
            "max_splits": self._max_splits,
            "min_split_pct": self._min_split_pct,
        }
