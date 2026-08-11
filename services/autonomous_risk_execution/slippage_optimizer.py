"""
Slippage Optimizer — minimizes execution slippage vs arrival price.

Models and optimizes:
    - Expected slippage = spread cost + market impact + delay cost
    - Optimal trade-off between speed and cost
    - Dynamic limit price placement
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class SlippageEstimate:
    """Estimated slippage for an order."""
    expected_slippage_bps: float = 0.0
    spread_cost_bps: float = 0.0
    impact_cost_bps: float = 0.0
    delay_cost_bps: float = 0.0
    volatility_cost_bps: float = 0.0
    total_cost_bps: float = 0.0
    confidence_interval: tuple[float, float] = (0.0, 0.0)


@dataclass
class SlippageResult:
    """Slippage optimization result."""
    id: str = field(default_factory=lambda: str(uuid4()))
    estimate: SlippageEstimate = field(default_factory=SlippageEstimate)
    optimal_participation: float = 0.10
    optimal_horizon_minutes: int = 30
    should_use_limit: bool = True
    optimal_limit_offset_bps: float = 3.0
    timestamp: datetime = field(default_factory=datetime.now)


class SlippageOptimizer:
    """
    Optimizes execution to minimize slippage.

    Slippage components:
        1. Spread cost: bid/ask spread × size
        2. Market impact: price movement from our trading
        3. Delay cost: price movement while waiting to execute
        4. Volatility cost: uncertainty in execution price

    Trade-off:
        Fast execution → low delay cost, high impact cost
        Slow execution → low impact cost, high delay cost
    """

    def __init__(self) -> None:
        self._last_results: dict[str, SlippageResult] = {}

    async def estimate(
        self,
        quantity: int,
        adv: float,
        spread_bps: float = 5.0,
        volatility: float = 0.15,
        participation: float = 0.10,
        time_horizon_min: int = 30,
        price: float = 100.0,
    ) -> SlippageEstimate:
        """Estimate expected slippage."""
        pct_adv = abs(quantity) / max(adv, 1)

        # Spread cost: half-spread × participation fraction
        spread_cost = spread_bps * 0.5 * min(pct_adv / participation, 1.0)

        # Market impact: square-root model
        # impact = σ * (Q/ADV)^0.5
        impact_cost = volatility * (pct_adv ** 0.5) * 100  # bps

        # Delay cost: volatility × sqrt(time) risk
        # More time = more opportunity for adverse price movement
        delay_cost = volatility * (time_horizon_min / 390) ** 0.5 * 50  # bps

        # Volatility cost during execution
        vol_cost = volatility * 0.10 * 100  # bps

        total = spread_cost + impact_cost + delay_cost + vol_cost

        return SlippageEstimate(
            expected_slippage_bps=total,
            spread_cost_bps=spread_cost,
            impact_cost_bps=impact_cost,
            delay_cost_bps=delay_cost,
            volatility_cost_bps=vol_cost,
            total_cost_bps=total,
            confidence_interval=(max(0, total * 0.5), total * 1.5),
        )

    async def optimize(
        self,
        quantity: int,
        adv: float,
        spread_bps: float = 5.0,
        volatility: float = 0.15,
        urgency: str = "MEDIUM",
    ) -> SlippageResult:
        """Find optimal execution parameters to minimize slippage."""
        pct_adv = abs(quantity) / max(adv, 1)

        # Test different participation rates
        best_cost = float("inf")
        best_config = (0.10, 30)

        urgency_limits = {
            "CRITICAL": (0.15, 0.25, 5, 15),
            "HIGH": (0.08, 0.20, 10, 30),
            "MEDIUM": (0.05, 0.15, 10, 60),
            "LOW": (0.02, 0.10, 20, 120),
        }
        min_part, max_part, min_t, max_t = urgency_limits.get(urgency, (0.05, 0.15, 10, 60))

        for part in [p / 100 for p in range(int(min_part * 100), int(max_part * 100) + 1, 2)]:
            for horizon in range(min_t, max_t + 1, 10):
                est = await self.estimate(
                    quantity, adv, spread_bps, volatility, part, horizon,
                )
                if est.total_cost_bps < best_cost:
                    best_cost = est.total_cost_bps
                    best_config = (part, horizon)

        opt_part, opt_horizon = best_config

        result = SlippageResult(
            optimal_participation=opt_part,
            optimal_horizon_minutes=opt_horizon,
            should_use_limit=spread_bps > 3.0,
            optimal_limit_offset_bps=spread_bps * 0.3,
        )
        result.estimate = await self.estimate(
            quantity, adv, spread_bps, volatility,
            opt_part, opt_horizon,
        )

        return result
