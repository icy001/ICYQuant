"""
Order Slicer — decomposes parent orders into child orders.

Adaptive slicing adjusts child order sizes in real-time based on:
    - Current liquidity conditions
    - Spread changes
    - Volatility changes
    - Fill rate
    - Remaining time
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class SliceConfig:
    """Configuration for order slicing."""
    num_slices: int = 10
    min_slice_pct: float = 0.03
    max_slice_pct: float = 0.20
    adaptive: bool = True
    min_slice_interval_seconds: int = 30
    participation_target: float = 0.10


@dataclass
class ChildOrderInfo:
    """Information about a child order slice."""
    id: str = field(default_factory=lambda: str(uuid4()))
    parent_id: str = ""
    seq: int = 0
    quantity: int = 0
    cumulative_quantity: int = 0
    sent: bool = False
    filled: bool = False
    fill_quantity: int = 0
    avg_fill_price: float = 0.0
    slippage_bps: float = 0.0
    timestamp: Optional[datetime] = None


@dataclass
class SlicePlan:
    """Complete order slicing plan."""
    id: str = field(default_factory=lambda: str(uuid4()))
    parent_order_size: int = 0
    children: list[ChildOrderInfo] = field(default_factory=list)
    config: SliceConfig = field(default_factory=SliceConfig)
    remaining_quantity: int = 0
    created_at: datetime = field(default_factory=datetime.now)


class OrderSlicer:
    """
    Adaptive order slicer.

    Core formula:
        child_qty_i = total * f_i(shape, i, n)
        where f_i distributes total across n slices

    Adaptive adjustments:
        If fill_rate_i > expected: increase next slice
        If spread has widened: decrease next slice
        If vol has increased: decrease next slice, increase count
        If approaching deadline: increase slice size
        If liquidity improved: increase slice size
    """

    def __init__(self, config: Optional[SliceConfig] = None) -> None:
        self._config = config or SliceConfig()
        self._active_plans: dict[str, SlicePlan] = {}

    async def slice(
        self, parent_id: str, total_quantity: int
    ) -> SlicePlan:
        """Create an initial slicing plan."""
        n = self._config.num_slices
        plan = SlicePlan(
            parent_order_size=total_quantity,
            remaining_quantity=total_quantity,
            config=self._config,
        )

        base_qty = total_quantity // n
        remainder = total_quantity - base_qty * n

        for i in range(n):
            qty = base_qty + (1 if i < remainder else 0)
            child = ChildOrderInfo(
                parent_id=parent_id, seq=i, quantity=qty,
            )
            plan.children.append(child)

        self._active_plans[plan.id] = plan
        logger.debug("Sliced %d into %d child orders", total_quantity, n)
        return plan

    async def adapt(
        self,
        plan_id: str,
        market_feedback: dict,
    ) -> Optional[ChildOrderInfo]:
        """
        Adaptively adjust next child order based on market conditions.

        Market feedback:
            - fill_rate: actual / expected fill rate
            - spread_ratio: current spread / initial spread
            - vol_ratio: current vol / initial vol
            - remaining_time_pct: remaining time / total time
        """
        plan = self._active_plans.get(plan_id)
        if not plan:
            return None

        # Find next unsent child
        next_child = None
        for child in plan.children:
            if not child.sent:
                next_child = child
                break

        if not next_child:
            return None

        # Adaptive adjustments
        fill_rate = market_feedback.get("fill_rate", 1.0)
        spread_ratio = market_feedback.get("spread_ratio", 1.0)
        vol_ratio = market_feedback.get("vol_ratio", 1.0)
        remaining_time = market_feedback.get("remaining_time_pct", 1.0)

        scale = 1.0
        # Higher fill rate → can increase size
        if fill_rate > 1.2:
            scale *= 1.15
        elif fill_rate < 0.5:
            scale *= 0.70

        # Wider spread → reduce size
        if spread_ratio > 1.5:
            scale *= 0.75

        # Higher vol → reduce size
        if vol_ratio > 1.5:
            scale *= 0.80

        # Running out of time → increase size
        if remaining_time < 0.30:
            scale *= 1.30
        elif remaining_time > 0.70:
            scale *= 0.90

        # Apply scale with constraints
        base_qty = plan.parent_order_size // len(plan.children)
        new_qty = int(base_qty * scale)
        new_qty = max(
            int(plan.parent_order_size * self._config.min_slice_pct),
            min(new_qty, int(plan.parent_order_size * self._config.max_slice_pct)),
        )
        new_qty = min(new_qty, plan.remaining_quantity)

        next_child.quantity = new_qty
        return next_child

    async def mark_sent(self, plan_id: str, child_id: str) -> None:
        """Mark a child order as sent."""
        plan = self._active_plans.get(plan_id)
        if plan:
            for child in plan.children:
                if child.id == child_id:
                    child.sent = True
                    child.timestamp = datetime.now()
                    plan.remaining_quantity -= child.quantity
                    break

    async def mark_filled(
        self, plan_id: str, child_id: str,
        fill_qty: int, avg_price: float, arrival_price: float,
    ) -> None:
        """Mark a child order as filled."""
        plan = self._active_plans.get(plan_id)
        if plan:
            for child in plan.children:
                if child.id == child_id:
                    child.filled = True
                    child.fill_quantity = fill_qty
                    child.avg_fill_price = avg_price
                    if arrival_price > 0:
                        child.slippage_bps = (
                            (avg_price - arrival_price) / arrival_price * 10_000
                            if child.sent and plan.parent_order_size > 0
                            else 0
                        )
                    break

    def get_next_unsent(self, plan_id: str) -> Optional[ChildOrderInfo]:
        """Get the next unsent child order."""
        plan = self._active_plans.get(plan_id)
        if not plan:
            return None
        for child in plan.children:
            if not child.sent:
                return child
        return None

    @property
    def active_plans(self) -> dict[str, SlicePlan]:
        return self._active_plans
