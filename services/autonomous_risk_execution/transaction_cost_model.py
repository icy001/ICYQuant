"""
Transaction Cost Model — comprehensive cost estimation.

Total transaction cost decomposition:
    TC = Commission + Spread Cost + Market Impact + Slippage + Opportunity Cost

Used to convert "gross alpha" to "net alpha" — the evolution objective.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class CostBreakdown:
    """Detailed transaction cost breakdown."""
    commission_bps: float = 0.0
    spread_cost_bps: float = 0.0
    market_impact_bps: float = 0.0
    slippage_bps: float = 0.0
    opportunity_cost_bps: float = 0.0
    total_cost_bps: float = 0.0


@dataclass
class TransactionCostEstimate:
    """Complete transaction cost estimate."""
    id: str = field(default_factory=lambda: str(uuid4()))
    asset: str = ""
    side: str = "BUY"
    quantity: int = 0
    notional: float = 0.0
    arrival_price: float = 0.0
    breakdown: CostBreakdown = field(default_factory=CostBreakdown)
    net_alpha_bps: float = 0.0
    gross_alpha_bps: float = 0.0
    timestamp: datetime = field(default_factory=datetime.now)


class TransactionCostModel:
    """
    Full transaction cost model.

    Components:
        1. Commission: Broker/exchange fees (fixed or per-share)
        2. Spread cost: Half-spread for crossing bid-ask
        3. Market impact: Price movement from our trading
        4. Slippage: Adverse price movement during execution
        5. Opportunity cost: Cost of NOT executing (for unfilled)

    Purpose: Evolution uses NET performance as optimization target.
    """

    def __init__(
        self, commission_per_share: float = 0.005,
        min_commission: float = 1.0,
    ) -> None:
        self._commission_per_share = commission_per_share
        self._min_commission = min_commission
        self._history: list[TransactionCostEstimate] = []

    async def estimate(
        self,
        asset: str,
        side: str,
        quantity: int,
        price: float,
        adv: float = 1_000_000,
        spread_bps: float = 5.0,
        volatility: float = 0.02,
        expected_impact_bps: float = 0.0,
        expected_slippage_bps: float = 0.0,
        gross_alpha_bps: float = 0.0,
    ) -> TransactionCostEstimate:
        """Estimate total transaction cost."""
        notional = abs(quantity) * price
        pct_adv = abs(quantity) / max(adv, 1)

        # Commission
        commission = max(
            abs(quantity) * self._commission_per_share,
            self._min_commission,
        )
        commission_bps = (commission / max(notional, 1)) * 10000

        # Spread cost: half-spread
        spread_cost = spread_bps * 0.5

        # Market impact
        if expected_impact_bps > 0:
            impact = expected_impact_bps
        else:
            impact = volatility * (pct_adv ** 0.5) * 100

        # Slippage
        slippage = expected_slippage_bps if expected_slippage_bps > 0 else volatility * 5

        # Total
        total = commission_bps + spread_cost + impact + slippage

        estimate = TransactionCostEstimate(
            asset=asset,
            side=side,
            quantity=quantity,
            notional=notional,
            arrival_price=price,
            breakdown=CostBreakdown(
                commission_bps=commission_bps,
                spread_cost_bps=spread_cost,
                market_impact_bps=impact,
                slippage_bps=slippage,
                total_cost_bps=total,
            ),
            gross_alpha_bps=gross_alpha_bps,
            net_alpha_bps=gross_alpha_bps - total,
        )

        self._history.append(estimate)
        if len(self._history) > 1000:
            self._history = self._history[-500:]

        return estimate

    async def estimate_portfolio_cost(
        self, orders: list[dict], prices: dict[str, float]
    ) -> dict[str, TransactionCostEstimate]:
        """Estimate costs for a portfolio of orders."""
        results = {}
        for order in orders:
            asset = order.get("asset", "")
            price = prices.get(asset, 100)
            est = await self.estimate(
                asset=asset,
                side=order.get("side", "BUY"),
                quantity=order.get("quantity", 0),
                price=price,
            )
            results[asset] = est
        return results

    @property
    def history(self) -> list[TransactionCostEstimate]:
        return self._history[-100:]
