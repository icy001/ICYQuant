"""
Execution Planner — creates detailed multi-slice execution plans.

Transforms a parent order into a concrete execution plan with:
    - Number of child orders (slices)
    - Size of each slice
    - Timing for each slice
    - Participation rate per slice
    - Adaptive adjustments
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class SliceShape(Enum):
    """Distribution shapes for order slicing."""
    UNIFORM = "uniform"
    FRONT_LOADED = "front_loaded"
    BACK_LOADED = "back_loaded"
    U_SHAPED = "u_shaped"
    VWAP = "vwap"


@dataclass
class ChildOrder:
    """A single child/slice order."""
    id: str = field(default_factory=lambda: str(uuid4()))
    parent_id: str = ""
    sequence: int = 0
    quantity: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    participation_pct: float = 0.10
    strategy: str = "LIMIT"
    limit_price: Optional[float] = None
    is_adaptive: bool = True


@dataclass
class ExecutionPlan:
    """Detailed execution plan."""
    id: str = field(default_factory=lambda: str(uuid4()))
    parent_order_id: str = ""
    asset: str = ""
    side: str = "BUY"
    total_quantity: int = 0
    filled_quantity: int = 0
    child_orders: list[ChildOrder] = field(default_factory=list)
    num_slices: int = 10
    time_horizon_min: int = 30
    slice_shape: SliceShape = SliceShape.VWAP
    max_participation: float = 0.10
    active: bool = True
    created_at: datetime = field(default_factory=datetime.now)


class ExecutionPlanner:
    """
    Creates and manages execution plans with child orders.

    Planning logic:
        1. Determine optimal number of slices
        2. Choose slice size distribution shape
        3. Calculate per-slice participation rate
        4. Set timing for each slice
        5. Enable adaptive rebalancing of remaining slices
    """

    def __init__(
        self,
        default_slices: int = 10,
        min_slice_pct: float = 0.05,
        max_slice_pct: float = 0.20,
    ) -> None:
        self._default_slices = default_slices
        self._min_slice_pct = min_slice_pct
        self._max_slice_pct = max_slice_pct
        self._active_plans: dict[str, ExecutionPlan] = {}

    async def create_plan(
        self,
        parent_id: str,
        asset: str,
        side: str,
        total_quantity: int,
        time_horizon_min: int = 30,
        adv: float = 1_000_000,
        volatility: float = 0.15,
        urgency: str = "MEDIUM",
        shape: SliceShape = SliceShape.VWAP,
    ) -> ExecutionPlan:
        """
        Create a detailed execution plan for a parent order.

        Args:
            parent_id: Parent order identifier
            asset: Asset symbol
            side: BUY or SELL
            total_quantity: Total order quantity
            time_horizon_min: Total execution time in minutes
            adv: Average daily volume
            volatility: Asset volatility
            urgency: Execution urgency
            shape: Slice distribution shape
        """
        # Determine number of slices
        urgency_slices = {"CRITICAL": 3, "HIGH": 5, "MEDIUM": 10, "LOW": 20}
        num_slices = urgency_slices.get(urgency, self._default_slices)

        # Cap slices based on time horizon
        min_interval = 2  # min minutes between slices
        max_possible = max(1, time_horizon_min // min_interval)
        num_slices = min(num_slices, max_possible)

        # Ensure min slice size
        min_qty = max(1, int(total_quantity * self._min_slice_pct))
        max_qty = int(total_quantity * self._max_slice_pct)
        if total_quantity / num_slices < min_qty:
            num_slices = max(1, total_quantity // min_qty)

        plan = ExecutionPlan(
            parent_order_id=parent_id,
            asset=asset,
            side=side,
            total_quantity=total_quantity,
            num_slices=num_slices,
            time_horizon_min=time_horizon_min,
            slice_shape=shape,
        )

        # Generate slice quantities
        quantities = self._compute_slice_quantities(total_quantity, num_slices, shape)
        interval_min = time_horizon_min / max(num_slices, 1)

        for i, qty in enumerate(quantities):
            child = ChildOrder(
                parent_id=parent_id,
                sequence=i,
                quantity=qty,
                start_time=datetime.now() + timedelta(minutes=i * interval_min),
                end_time=datetime.now() + timedelta(minutes=(i + 1) * interval_min),
                participation_pct=min(self._max_slice_pct, qty / max(adv, 1)),
            )
            plan.child_orders.append(child)

        self._active_plans[plan.id] = plan

        logger.info(
            "Plan created: %s %s %d shares → %d slices over %d min",
            asset, side, total_quantity, num_slices, time_horizon_min,
        )
        return plan

    def _compute_slice_quantities(
        self, total: int, n: int, shape: SliceShape
    ) -> list[int]:
        """Compute quantities for each slice based on distribution shape."""
        if n <= 0:
            return []
        if n == 1:
            return [total]

        if shape == SliceShape.UNIFORM:
            base = total // n
            remainder = total - base * n
            return [base + (1 if i < remainder else 0) for i in range(n)]

        elif shape == SliceShape.FRONT_LOADED:
            # Decreasing: more at beginning
            weights = [n - i for i in range(n)]
            total_w = sum(weights)
            return [total * w // total_w for w in weights]

        elif shape == SliceShape.BACK_LOADED:
            # Increasing: more at end
            weights = [i + 1 for i in range(n)]
            total_w = sum(weights)
            return [total * w // total_w for w in weights]

        elif shape == SliceShape.VWAP:
            # Volume-weighted: typical profile
            half = n // 2
            weights = (
                list(range(1, half + 1))
                + list(range(half, 0, -1))
            )
            if len(weights) < n:
                weights.insert(len(weights) // 2, half + 1)
            total_w = sum(weights)
            quantities = [total * w // total_w for w in weights]
            # Adjust for rounding
            diff = total - sum(quantities)
            if diff > 0:
                mid = n // 2
                quantities[mid] += diff
            return quantities

        else:  # U_SHAPED
            half = n // 2
            weights = (
                list(range(half, 0, -1))
                + list(range(1, half + 1))
            )
            if len(weights) < n:
                weights.append(1)
            total_w = sum(weights)
            quantities = [total * w // total_w for w in weights]
            diff = total - sum(quantities)
            if diff > 0:
                quantities[0] += diff
            return quantities

    async def update_progress(
        self, plan_id: str, filled_quantity: int
    ) -> ExecutionPlan:
        """Update execution progress and adapt remaining slices."""
        plan = self._active_plans.get(plan_id)
        if not plan:
            raise ValueError(f"Plan {plan_id} not found")

        plan.filled_quantity += filled_quantity
        remaining = plan.total_quantity - plan.filled_quantity

        # Adapt remaining slices
        remaining_children = [c for c in plan.child_orders if c.quantity > 0]
        if remaining > 0 and remaining_children:
            even_qty = remaining // len(remaining_children)
            for child in remaining_children:
                child.quantity = even_qty

        # Check completion
        if plan.filled_quantity >= plan.total_quantity:
            plan.active = False
            logger.info("Plan %s completed", plan_id)

        return plan

    def get_plan(self, plan_id: str) -> Optional[ExecutionPlan]:
        return self._active_plans.get(plan_id)

    def get_active_plans(self) -> list[ExecutionPlan]:
        return [p for p in self._active_plans.values() if p.active]
