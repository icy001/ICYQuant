"""
Child Order Generator — generates concrete child orders ready for OMS.

Each child order includes:
    - Asset, side, quantity
    - Order type (LIMIT, MARKET)
    - Limit price (if applicable)
    - Time-in-force
    - Venue
    - Parent trace ID
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class ChildOrder:
    """A concrete child order ready for submission."""
    id: str = field(default_factory=lambda: str(uuid4()))
    parent_id: str = ""
    execution_plan_id: str = ""
    slice_seq: int = 0
    asset: str = ""
    side: str = "BUY"
    quantity: int = 0
    order_type: str = "LIMIT"
    limit_price: Optional[float] = None
    time_in_force: str = "DAY"
    venue: str = "SMART"
    max_participation: float = 0.10
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class ChildOrderBatch:
    """A batch of child orders."""
    id: str = field(default_factory=lambda: str(uuid4()))
    orders: list[ChildOrder] = field(default_factory=list)
    total_quantity: int = 0
    total_notional: float = 0.0
    created_at: datetime = field(default_factory=datetime.now)


class ChildOrderGenerator:
    """
    Generates OMS-ready child orders from execution plans.

    Transforms abstract slice quantities into complete order messages
    with proper routing, limits, and metadata.

    Order types:
        - LIMIT: With price limit, passive
        - MARKET: Immediate execution, aggressive
        - RELATIVE: Pegged to market (arrival price, midpoint)
    """

    def __init__(self, default_time_in_force: str = "DAY") -> None:
        self._default_tif = default_time_in_force
        self._generated_count: int = 0

    async def generate(
        self,
        parent_id: str,
        plan_id: str,
        asset: str,
        side: str,
        quantities: list[int],
        reference_price: Optional[float] = None,
        spread_bps: float = 5.0,
        strategy: str = "TWAP",
        venue: str = "SMART",
    ) -> list[ChildOrder]:
        """
        Generate child orders from a list of quantities.

        Args:
            parent_id: Parent order ID
            plan_id: Execution plan ID
            asset: Asset symbol
            side: BUY or SELL
            quantities: List of child order quantities
            reference_price: Current market price
            spread_bps: Current bid-ask spread
            strategy: Execution strategy
            venue: Target venue
        """
        orders = []

        for seq, qty in enumerate(quantities):
            if qty <= 0:
                continue

            order_type = self._determine_order_type(strategy, seq)
            limit_price = self._compute_limit_price(
                reference_price, spread_bps, side, order_type,
            )

            child = ChildOrder(
                parent_id=parent_id,
                execution_plan_id=plan_id,
                slice_seq=seq,
                asset=asset,
                side=side,
                quantity=qty,
                order_type=order_type,
                limit_price=limit_price,
                time_in_force=self._default_tif,
                venue=venue,
            )
            orders.append(child)
            self._generated_count += 1

        logger.debug("Generated %d child orders for parent %s", len(orders), parent_id)
        return orders

    def _determine_order_type(self, strategy: str, seq: int) -> str:
        """Determine order type based on strategy and position in sequence."""
        strategy_map = {
            "MARKET": "MARKET",
            "LIMIT": "LIMIT",
            "TWAP": "LIMIT",
            "VWAP": "LIMIT",
            "POV": "LIMIT",
            "ADAPTIVE": "LIMIT",
            "ICEBERG": "LIMIT",
        }
        return strategy_map.get(strategy.upper(), "LIMIT")

    def _compute_limit_price(
        self,
        reference: Optional[float],
        spread_bps: float,
        side: str,
        order_type: str,
    ) -> Optional[float]:
        """Compute aggressive/passive limit price."""
        if order_type == "MARKET" or reference is None:
            return None

        # Passive: place at opposite side to get better fill
        half_spread = spread_bps / 10_000 * reference * 0.5

        if side.upper() == "BUY":
            # Buy: place at bid (slightly below mid)
            return round(reference - half_spread, 4)
        else:
            # Sell: place at ask (slightly above mid)
            return round(reference + half_spread, 4)

    def create_batch(self, orders: list[ChildOrder]) -> ChildOrderBatch:
        """Create a batch from a list of child orders."""
        batch = ChildOrderBatch(
            orders=orders,
            total_quantity=sum(o.quantity for o in orders),
        )
        return batch

    @property
    def generated_count(self) -> int:
        return self._generated_count
