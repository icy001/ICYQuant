"""
Execution Cost Estimator — unified pre-trade cost estimation.

Integrates all cost components into a single pre-trade estimate:
    - Spread cost (from SpreadModel)
    - Market impact (from MarketImpactModel)
    - Transaction costs (from TransactionCostModel)
    - Slippage (from SlippageOptimizer)

Used by the Pre-Trade Optimizer to decide ALLOW/RESIZE/REJECT.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class CostEstimate:
    """Unified execution cost estimate."""
    id: str = field(default_factory=lambda: str(uuid4()))
    asset: str = ""
    side: str = "BUY"
    quantity: int = 0
    notional: float = 0.0

    # Cost components
    commission_bps: float = 0.0
    spread_cost_bps: float = 0.0
    market_impact_bps: float = 0.0
    slippage_bps: float = 0.0
    total_cost_bps: float = 0.0
    total_cost_notional: float = 0.0

    # Risk
    confidence_95_high: float = 0.0

    # Decision
    is_acceptable: bool = True
    reason: str = ""
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class BatchCostEstimate:
    """Cost estimate for a batch of orders."""
    id: str = field(default_factory=lambda: str(uuid4()))
    estimates: list[CostEstimate] = field(default_factory=list)
    total_notional: float = 0.0
    avg_cost_bps: float = 0.0
    max_cost_bps: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class ExecutionCostEstimator:
    """
    Unified pre-trade cost estimator.

    Aggregates all cost models into a single estimate per order.

    Cost thresholds:
        < 10 bps: Excellent, no concerns
        10-30 bps: Acceptable
        30-50 bps: Borderline, review needed
        > 50 bps: Unacceptable, resize or reject
    """

    COST_THRESHOLDS = [
        (10, "EXCELLENT"),
        (30, "ACCEPTABLE"),
        (50, "BORDERLINE"),
        (float("inf"), "UNACCEPTABLE"),
    ]

    def __init__(
        self,
        max_acceptable_cost_bps: float = 50.0,
    ) -> None:
        self._max_cost = max_acceptable_cost_bps
        self._history: list[CostEstimate] = []

    async def estimate(
        self,
        asset: str,
        side: str,
        quantity: int,
        price: float,
        adv: float = 1_000_000,
        spread_bps: float = 5.0,
        volatility: float = 0.02,
        commission_per_share: float = 0.005,
    ) -> CostEstimate:
        """Estimate total execution cost for a single order."""
        notional = abs(quantity) * price
        pct_adv = abs(quantity) / max(adv, 1)

        # Commission
        commission = max(abs(quantity) * commission_per_share, 1.0)
        commission_bps = (commission / max(notional, 1)) * 10000

        # Spread cost (half-spread)
        spread_cost = spread_bps * 0.5

        # Market impact (square-root model)
        impact = volatility * (pct_adv ** 0.5) * 100

        # Slippage buffer
        slippage = volatility * 3

        total = commission_bps + spread_cost + impact + slippage

        # Acceptability
        is_ok = total <= self._max_cost
        for threshold, label in self.COST_THRESHOLDS:
            if total <= threshold:
                reason = label
                break
        else:
            reason = "UNACCEPTABLE"

        estimate = CostEstimate(
            asset=asset, side=side, quantity=quantity, notional=notional,
            commission_bps=commission_bps,
            spread_cost_bps=spread_cost,
            market_impact_bps=impact,
            slippage_bps=slippage,
            total_cost_bps=total,
            total_cost_notional=notional * total / 10000,
            confidence_95_high=total * 1.5,
            is_acceptable=is_ok,
            reason=reason,
        )
        self._history.append(estimate)
        if len(self._history) > 500:
            self._history = self._history[-250:]

        return estimate

    async def estimate_batch(
        self, orders: list[dict], prices: dict[str, float]
    ) -> BatchCostEstimate:
        """Estimate costs for a batch of orders."""
        batch = BatchCostEstimate()
        total_notional = 0.0
        total_cost_weighted = 0.0
        max_cost = 0.0

        for order in orders:
            asset = order.get("asset", "")
            price = prices.get(asset, 100)
            est = await self.estimate(
                asset=asset,
                side=order.get("side", "BUY"),
                quantity=order.get("quantity", 0),
                price=price,
            )
            batch.estimates.append(est)
            total_notional += est.notional
            total_cost_weighted += est.total_cost_bps * est.notional
            max_cost = max(max_cost, est.total_cost_bps)

        batch.total_notional = total_notional
        batch.avg_cost_bps = total_cost_weighted / max(total_notional, 1)
        batch.max_cost_bps = max_cost
        return batch

    @property
    def history(self) -> list[CostEstimate]:
        return self._history[-100:]
