"""
Execution Optimizer — transforms risk-adjusted targets into optimal execution plans.

Answers: "Given what I need to trade, how do I execute it to minimize cost?"

Optimization dimensions:
    - Execution strategy selection (TWAP, VWAP, POV, Adaptive, etc.)
    - Order slicing (parent → child orders)
    - Participation rate control
    - Timing and urgency
    - Venue and liquidity routing
    - Market impact minimization
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class ExecutionStrategy(Enum):
    """Available execution strategies."""
    MARKET = "market"
    LIMIT = "limit"
    TWAP = "twap"
    VWAP = "vwap"
    POV = "pov"
    ADAPTIVE = "adaptive"
    LIQUIDITY_SEEKING = "liquidity_seeking"
    IMPLEMENTATION_SHORTFALL = "implementation_shortfall"
    ICEBERG = "iceberg"
    DARK_POOL = "dark_pool"


class Urgency(Enum):
    """Execution urgency levels."""
    CRITICAL = "critical"  # Execute immediately, accept some cost
    HIGH = "high"  # Complete within minutes
    MEDIUM = "medium"  # Complete within 30-60 min
    LOW = "low"  # Patient execution, prioritize cost


@dataclass
class ExecutionOrder:
    """A single order to execute."""
    asset: str
    side: str  # BUY, SELL
    quantity: int
    strategy: ExecutionStrategy = ExecutionStrategy.VWAP
    urgency: Urgency = Urgency.MEDIUM
    time_horizon_min: int = 30
    max_participation: float = 0.10
    limit_price: Optional[float] = None
    venue: str = "SMART"
    constraints: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    """Complete execution plan."""
    id: str = field(default_factory=lambda: str(uuid4()))
    orders: list[ExecutionOrder] = field(default_factory=list)
    total_notional: float = 0.0
    expected_cost_bps: float = 0.0
    expected_impact_bps: float = 0.0
    time_horizon_min: int = 30
    slices_per_order: int = 10
    strategy: ExecutionStrategy = ExecutionStrategy.VWAP
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ExecutionOptimizationResult:
    """Result of execution optimization."""
    id: str = field(default_factory=lambda: str(uuid4()))
    plan: ExecutionPlan = field(default_factory=ExecutionPlan)
    warnings: list[str] = field(default_factory=list)
    optimization_insights: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


class ExecutionOptimizer:
    """
    Autonomous execution optimization engine.

    Pipeline:
        1. Select execution strategy per order
        2. Determine urgency based on alpha decay
        3. Create execution plan with slicing
        4. Estimate costs and market impact
        5. Select venues and route orders
        6. Generate child order schedule
    """

    def __init__(self) -> None:
        self._last_result: Optional[ExecutionOptimizationResult] = None

    async def optimize(
        self,
        risk_adjusted_target: dict[str, float],
        alpha_decay_hours: Optional[dict[str, float]] = None,
        market_data: Optional[dict[str, dict]] = None,
        default_strategy: ExecutionStrategy = ExecutionStrategy.VWAP,
    ) -> ExecutionOptimizationResult:
        """
        Generate optimal execution plan from risk-adjusted targets.

        Args:
            risk_adjusted_target: {asset: weight}
            alpha_decay_hours: {asset: alpha_half_life_hours}
            market_data: {asset: {spread, volatility, adv, ...}}
            default_strategy: Default execution strategy

        Returns:
            Execution optimization result with plan
        """
        result = ExecutionOptimizationResult()
        plan = ExecutionPlan(strategy=default_strategy)

        alpha_decay = alpha_decay_hours or {}
        mkt = market_data or {}
        total_notional = 0.0

        for asset, weight in risk_adjusted_target.items():
            asset_data = mkt.get(asset, {})
            adv = asset_data.get("adv", 10_000_000)
            quantity = int(abs(weight) * 1_000_000)  # Simplified

            # Determine urgency from alpha decay
            decay_hours = alpha_decay.get(asset, 24)
            urgency = self._decay_to_urgency(decay_hours)

            # Select strategy
            strategy = self._select_strategy(
                quantity, adv, asset_data.get("spread_bps", 5),
                asset_data.get("volatility", 0.15), urgency,
            )

            order = ExecutionOrder(
                asset=asset,
                side="BUY" if weight > 0 else "SELL",
                quantity=quantity,
                strategy=strategy,
                urgency=urgency,
                time_horizon_min=self._compute_time_horizon(urgency, quantity, adv),
                max_participation=min(0.15, adv / max(abs(weight), 1)),
            )
            plan.orders.append(order)
            total_notional += abs(quantity)

        plan.total_notional = total_notional

        # Estimate costs
        plan.expected_cost_bps = await self._estimate_cost(plan, mkt)
        plan.expected_impact_bps = await self._estimate_impact(plan, mkt)
        plan.slices_per_order = 10

        result.plan = plan
        result.timestamp = datetime.now()
        self._last_result = result

        logger.info(
            "Execution plan: %d orders, cost=%.1fbps, impact=%.1fbps",
            len(plan.orders), plan.expected_cost_bps, plan.expected_impact_bps,
        )
        return result

    # ── Strategy Selection ─────────────────────────────────────

    def _select_strategy(
        self,
        quantity: int,
        adv: float,
        spread_bps: float,
        volatility: float,
        urgency: Urgency,
    ) -> ExecutionStrategy:
        """Select optimal execution strategy."""
        pct_adv = abs(quantity) / max(adv, 1)

        if urgency == Urgency.CRITICAL:
            return ExecutionStrategy.MARKET
        if urgency == Urgency.HIGH:
            return ExecutionStrategy.ADAPTIVE if pct_adv > 0.05 else ExecutionStrategy.VWAP
        if spread_bps > 20:
            return ExecutionStrategy.LIMIT
        if pct_adv > 0.15:
            return ExecutionStrategy.ICEBERG
        if volatility > 0.40:
            return ExecutionStrategy.ADAPTIVE

        return ExecutionStrategy.VWAP

    def _decay_to_urgency(self, decay_hours: float) -> Urgency:
        """Map alpha decay half-life to execution urgency."""
        if decay_hours < 0.5:
            return Urgency.CRITICAL
        if decay_hours < 2:
            return Urgency.HIGH
        if decay_hours < 8:
            return Urgency.MEDIUM
        return Urgency.LOW

    def _compute_time_horizon(
        self, urgency: Urgency, quantity: int, adv: float
    ) -> int:
        """Compute recommended execution time horizon in minutes."""
        pct_adv = abs(quantity) / max(adv, 1)
        base = {
            Urgency.CRITICAL: 5, Urgency.HIGH: 15,
            Urgency.MEDIUM: 45, Urgency.LOW: 120,
        }
        minutes = base.get(urgency, 30)
        if pct_adv > 0.10:
            minutes *= 1.5
        return int(minutes)

    async def _estimate_cost(self, plan: ExecutionPlan, market_data: dict) -> float:
        """Estimate total execution cost in bps."""
        total_cost = 0.0
        total_value = max(plan.total_notional, 1)
        for order in plan.orders:
            mkt = market_data.get(order.asset, {})
            spread = mkt.get("spread_bps", 5)
            cost = spread * 0.5  # Half-spread cost
            total_cost += cost * abs(order.quantity) / total_value
        return total_cost

    async def _estimate_impact(self, plan: ExecutionPlan, market_data: dict) -> float:
        """Estimate market impact in bps."""
        total_impact = 0.0
        for order in plan.orders:
            mkt = market_data.get(order.asset, {})
            adv = max(mkt.get("adv", 10_000_000), 1)
            vol = mkt.get("volatility", 0.15)
            pct_adv = abs(order.quantity) / adv
            impact = vol * (pct_adv ** 0.5) * 100  # bps
            total_impact += impact
        return total_impact / max(len(plan.orders), 1)

    @property
    def last_result(self) -> Optional[ExecutionOptimizationResult]:
        return self._last_result
