"""Execution Algorithms — TWAP, VWAP, POV implementation.

Each algorithm implements the logic for slicing and adapting
execution to minimize costs under different market conditions.
"""

from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from .models import (
    ExecutionAlgorithm,
    ExecutionPlan,
    ExecutionSlice,
    ExecutionTask,
    MarketState,
    PlanStatus,
)
from .slicer import OrderSlicer


class TwapExecutor:
    """TWAP (Time-Weighted Average Price) executor.

    Distributes orders equally over time to achieve the average
    price over the execution window. Best for:
    - Stable, liquid markets
    - Medium/low urgency orders
    - Minimizing market impact
    """

    def __init__(self, default_slices: int = 20):
        self.slicer = OrderSlicer(default_slices=default_slices)

    def generate_plan(
        self,
        task: ExecutionTask,
        market_state: Optional[MarketState] = None,
    ) -> ExecutionPlan:
        """Generate a TWAP execution plan."""
        task.algorithm = ExecutionAlgorithm.TWAP
        slices = self.slicer.slice(task, market_state)

        total_qty = sum(s.quantity for s in slices)
        plan = ExecutionPlan(
            plan_id=f"PLAN_{task.order_id}_TWAP",
            order_id=task.order_id,
            algorithm=ExecutionAlgorithm.TWAP,
            total_quantity=task.quantity,
            slices=slices,
            duration_minutes=task.max_duration_minutes,
        )

        return plan


class VwapExecutor:
    """VWAP (Volume-Weighted Average Price) executor.

    Distributes orders according to historical volume profiles,
    executing more during high-volume periods. Best for:
    - Large orders in liquid markets
    - Benchmark-sensitive execution
    - ETF/index rebalancing
    """

    def __init__(self, default_slices: int = 26):
        self.slicer = OrderSlicer(default_slices=default_slices)

    def generate_plan(
        self,
        task: ExecutionTask,
        market_state: Optional[MarketState] = None,
    ) -> ExecutionPlan:
        """Generate a VWAP execution plan."""
        task.algorithm = ExecutionAlgorithm.VWAP
        slices = self.slicer.slice(task, market_state)

        plan = ExecutionPlan(
            plan_id=f"PLAN_{task.order_id}_VWAP",
            order_id=task.order_id,
            algorithm=ExecutionAlgorithm.VWAP,
            total_quantity=task.quantity,
            slices=slices,
            duration_minutes=task.max_duration_minutes,
        )

        return plan


class PovExecutor:
    """POV (Percentage Of Volume) executor.

    Maintains a constant participation rate of market volume,
    adapting slice sizes dynamically. Best for:
    - Minimizing information leakage
    - Large orders relative to market volume
    - Dynamic market conditions
    """

    def __init__(self):
        self.slicer = OrderSlicer()

    def generate_plan(
        self,
        task: ExecutionTask,
        market_state: Optional[MarketState] = None,
    ) -> ExecutionPlan:
        """Generate a POV execution plan."""
        task.algorithm = ExecutionAlgorithm.POV
        slices = self.slicer.slice(task, market_state)

        plan = ExecutionPlan(
            plan_id=f"PLAN_{task.order_id}_POV",
            order_id=task.order_id,
            algorithm=ExecutionAlgorithm.POV,
            total_quantity=task.quantity,
            slices=slices,
            duration_minutes=task.max_duration_minutes,
        )

        return plan


class AdaptiveExecutor:
    """Adaptive executor that selects the best algorithm dynamically.

    Considers:
    - Order size relative to daily volume (participation rate)
    - Market volatility
    - Spread costs
    - Urgency level
    """

    def __init__(self):
        self.twap = TwapExecutor()
        self.vwap = VwapExecutor()
        self.pov = PovExecutor()

    def select_algorithm(
        self,
        task: ExecutionTask,
        market_state: MarketState,
    ) -> ExecutionAlgorithm:
        """Select the best algorithm based on market conditions.

        Heuristics:
        - Large orders (>5% ADV) in volatile markets → POV
        - Large orders in stable markets → VWAP
        - Medium/small orders → TWAP
        - High urgency → fewer slices, TWAP
        - High spread → POV to be more opportunistic
        """
        adv = market_state.daily_volume
        participation = task.quantity / adv if adv > 0 else 1.0

        if task.urgency == "CRITICAL":
            return ExecutionAlgorithm.TWAP  # Fast execution

        if task.urgency == "HIGH":
            # Balance speed and cost — TWAP with fewer slices
            return ExecutionAlgorithm.TWAP

        if participation > 0.10:
            # Very large order — need volume-aware execution
            if market_state.volatility_20d > 0.30:
                return ExecutionAlgorithm.POV
            return ExecutionAlgorithm.VWAP

        if participation > 0.05:
            if market_state.spread_bps > 20:
                return ExecutionAlgorithm.POV
            return ExecutionAlgorithm.VWAP

        # Small/medium order in normal conditions
        if market_state.spread_bps > 30:
            return ExecutionAlgorithm.POV

        return ExecutionAlgorithm.TWAP

    def generate_plan(
        self,
        task: ExecutionTask,
        market_state: MarketState,
    ) -> ExecutionPlan:
        """Generate a plan using the best algorithm for current conditions."""
        algo = self.select_algorithm(task, market_state)

        if algo == ExecutionAlgorithm.TWAP:
            return self.twap.generate_plan(task, market_state)
        elif algo == ExecutionAlgorithm.VWAP:
            return self.vwap.generate_plan(task, market_state)
        else:
            return self.pov.generate_plan(task, market_state)
