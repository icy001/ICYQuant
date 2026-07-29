"""Execution Optimizer — selects the best execution strategy.

Orchestrates the full optimization pipeline:
1. Analyze the task and market state
2. Select the best execution algorithm
3. Generate execution plan with slices
4. Estimate costs (impact, slippage, spread)
5. Return the optimal execution plan
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from .algorithms import AdaptiveExecutor, PovExecutor, TwapExecutor, VwapExecutor
from .impact_model import MarketImpactModel
from .models import (
    ExecutionAlgorithm,
    ExecutionOutcome,
    ExecutionPlan,
    ExecutionQuality,
    ExecutionTask,
    ImpactEstimate,
    MarketState,
    OrderUrgency,
    PlanStatus,
)


class ExecutionOptimizer:
    """Optimizes order execution by selecting the best algorithm.

    The optimizer:
    1. Analyzes market conditions and order characteristics
    2. Selects the optimal execution algorithm
    3. Generates a sliced execution plan
    4. Estimates total execution costs
    5. Produces a quality score for the plan
    """

    def __init__(
        self,
        impact_model: Optional[MarketImpactModel] = None,
        default_slices: int = 20,
    ):
        """Initialize the execution optimizer.

        Args:
            impact_model: Market impact model instance.
            default_slices: Default slice count for TWAP/VWAP.
        """
        self.impact_model = impact_model or MarketImpactModel()
        self.twap = TwapExecutor(default_slices=default_slices)
        self.vwap = VwapExecutor(default_slices=default_slices)
        self.pov = PovExecutor()
        self.adaptive = AdaptiveExecutor()

    def optimize(
        self,
        task: ExecutionTask,
        market_state: MarketState,
        arrival_price: Optional[float] = None,
    ) -> ExecutionPlan:
        """Generate the optimal execution plan for a task.

        Args:
            task: The execution task.
            market_state: Current market conditions.
            arrival_price: Price at decision time (defaults to mid).

        Returns:
            An optimized ExecutionPlan.
        """
        arrival = arrival_price or market_state.mid_price

        # Select and generate plan
        if task.algorithm == ExecutionAlgorithm.ADAPTIVE:
            plan = self.adaptive.generate_plan(task, market_state)
        elif task.algorithm == ExecutionAlgorithm.TWAP:
            plan = self.twap.generate_plan(task, market_state)
        elif task.algorithm == ExecutionAlgorithm.VWAP:
            plan = self.vwap.generate_plan(task, market_state)
        elif task.algorithm == ExecutionAlgorithm.POV:
            plan = self.pov.generate_plan(task, market_state)
        else:
            plan = self.adaptive.generate_plan(task, market_state)

        # Estimate costs
        is_buy = task.side == "BUY"
        impact = self.impact_model.estimate_sliced(
            symbol=task.symbol,
            total_quantity=task.quantity,
            num_slices=max(plan.slice_count, 1),
            market_state=market_state,
            is_buy=is_buy,
        )

        plan.expected_impact_bps = impact.total_impact_bps

        # Estimate slippage (volatility × sqrt(time))
        import math
        vol = market_state.volatility_20d
        time_years = plan.duration_minutes / (252 * 390)  # Fraction of year
        slippage_frac = vol * math.sqrt(time_years)
        plan.expected_slippage_bps = round(slippage_frac * 10000, 2)

        # Estimate total cost
        total_cost_rate = (plan.expected_impact_bps + plan.expected_slippage_bps) / 10000
        plan.estimated_cost = round(arrival * task.quantity * total_cost_rate, 2)

        # Set slice-level impact estimates
        if plan.slices and impact.total_impact_bps > 0:
            per_slice_impact = impact.total_impact_bps / plan.slice_count
            for s in plan.slices:
                s.expected_impact_bps = round(per_slice_impact, 2)

        plan.status = PlanStatus.CREATED
        return plan

    def evaluate_outcome(
        self,
        plan: ExecutionPlan,
        arrival_price: float,
        average_execution_price: float,
        vwap_price: float = 0.0,
        commission: float = 0.0,
    ) -> ExecutionOutcome:
        """Evaluate the outcome of an executed plan.

        Args:
            plan: The execution plan that was executed.
            arrival_price: Price at decision time.
            average_execution_price: Volume-weighted average execution price.
            vwap_price: Market VWAP over execution period.
            commission: Total commission paid.

        Returns:
            ExecutionOutcome with quality assessment.
        """
        # Slippage: execution price vs arrival price
        if arrival_price > 0:
            slippage_bps = (
                (average_execution_price - arrival_price) / arrival_price * 10000
            )
        else:
            slippage_bps = 0.0

        # Implementation shortfall
        impl_shortfall = slippage_bps + (plan.expected_impact_bps or 0.0)

        # Cost including commission
        total_notional = average_execution_price * plan.executed_quantity
        commission_bps = 0.0
        if total_notional > 0:
            commission_bps = commission / total_notional * 10000

        total_cost = abs(slippage_bps) + commission_bps

        # Quality assessment
        quality = self._assess_quality(
            slippage_bps=abs(slippage_bps),
            expected_impact=plan.expected_impact_bps,
            fill_rate=plan.fill_pct,
        )

        # Count filled slices
        slices_filled = sum(
            1 for s in plan.slices if s.status == "FILLED"
        )

        return ExecutionOutcome(
            order_id=plan.order_id,
            plan_id=plan.plan_id,
            algorithm=plan.algorithm,
            total_quantity=plan.total_quantity,
            executed_quantity=plan.executed_quantity,
            average_price=average_execution_price,
            arrival_price=arrival_price,
            vwap_price=vwap_price,
            slippage_bps=round(slippage_bps, 2),
            impact_bps=round(plan.expected_impact_bps, 2),
            implementation_shortfall_bps=round(impl_shortfall, 2),
            commission=commission,
            total_cost=round(total_cost, 2),
            quality=quality,
            duration_minutes=plan.duration_minutes,
            slices_filled=slices_filled,
            slices_total=plan.slice_count,
        )

    def _assess_quality(
        self,
        slippage_bps: float,
        expected_impact: float,
        fill_rate: float,
    ) -> ExecutionQuality:
        """Assess execution quality based on outcome metrics.

        Args:
            slippage_bps: Absolute slippage in basis points.
            expected_impact: Expected impact in basis points.
            fill_rate: Fill rate (0–1).

        Returns:
            ExecutionQuality rating.
        """
        # Combined score
        if slippage_bps < 2.0 and fill_rate > 0.99:
            return ExecutionQuality.EXCELLENT
        elif slippage_bps < 5.0 and fill_rate > 0.95:
            return ExecutionQuality.GOOD
        elif slippage_bps < 15.0 and fill_rate > 0.85:
            return ExecutionQuality.FAIR
        else:
            return ExecutionQuality.POOR

    def get_recommendation(
        self,
        task: ExecutionTask,
        market_state: MarketState,
    ) -> Dict[str, Any]:
        """Get execution recommendation without creating a full plan.

        Args:
            task: The execution task.
            market_state: Market conditions.

        Returns:
            Dict with algorithm recommendation and estimated metrics.
        """
        algo = self.adaptive.select_algorithm(task, market_state)

        # Estimate impact
        is_buy = task.side == "BUY"
        impact = self.impact_model.estimate(
            symbol=task.symbol,
            order_quantity=task.quantity,
            market_state=market_state,
            is_buy=is_buy,
        )

        # Determine optimal slice count
        if algo == ExecutionAlgorithm.TWAP:
            slices = 20
            duration = task.max_duration_minutes
        elif algo == ExecutionAlgorithm.VWAP:
            slices = 26
            duration = task.max_duration_minutes
        else:
            slices = 60
            duration = task.max_duration_minutes

        return {
            "symbol": task.symbol,
            "quantity": task.quantity,
            "side": task.side.value,
            "recommended_algorithm": algo.value,
            "estimated_impact_bps": impact.total_impact_bps,
            "estimated_impact_pct": f"{impact.total_impact_bps / 100:.3%}",
            "recommended_slices": slices,
            "duration_minutes": duration,
            "participation_rate": f"{impact.participation_rate:.2%}",
            "market_volatility": market_state.volatility_20d,
            "market_spread_bps": market_state.spread_bps,
        }
