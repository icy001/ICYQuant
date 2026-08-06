"""Transaction Cost Optimizer — optimize trades considering real execution costs.

Considers commission, slippage, liquidity constraints, and market
impact when generating trade execution plans.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class CostTrade:
    """A trade with estimated transaction costs."""

    asset: str
    trade_size: float
    action: str
    commission: float = 0.0
    slippage: float = 0.0
    market_impact: float = 0.0
    total_cost: float = 0.0
    cost_bps: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset": self.asset,
            "trade_size": self.trade_size,
            "action": self.action,
            "commission": self.commission,
            "slippage": self.slippage,
            "market_impact": self.market_impact,
            "total_cost": self.total_cost,
            "cost_bps": self.cost_bps,
        }


@dataclass
class CostOptimizedPlan:
    """Cost-optimized execution plan."""

    portfolio_id: str
    trades: List[CostTrade] = field(default_factory=list)
    total_commission: float = 0.0
    total_slippage: float = 0.0
    total_market_impact: float = 0.0
    total_cost: float = 0.0
    total_cost_bps: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "trades": [t.to_dict() for t in self.trades],
            "total_commission": self.total_commission,
            "total_slippage": self.total_slippage,
            "total_market_impact": self.total_market_impact,
            "total_cost": self.total_cost,
            "total_cost_bps": self.total_cost_bps,
            "num_trades": len(self.trades),
            "metadata": self.metadata,
        }


class TransactionCostOptimizer:
    """Optimize trades accounting for real execution costs.

    Models commission, slippage, and market impact to produce
    realistic cost estimates for portfolio rebalancing.
    """

    def __init__(self) -> None:
        # Default cost parameters
        self._commission_rate: float = 0.0003  # 3 bps
        self._slippage_rate: float = 0.0010  # 10 bps
        self._impact_factor: float = 0.1  # sqrt impact coefficient
        self._min_commission: float = 5.0  # minimum per trade

    async def optimize(
        self,
        portfolio_id: str,
        trades: List[Dict[str, Any]],
        capital: float = 1_000_000.0,
        adv_data: Optional[Dict[str, float]] = None,
        commission_rate: Optional[float] = None,
        slippage_rate: Optional[float] = None,
    ) -> CostOptimizedPlan:
        """Estimate transaction costs for each trade."""

        comm = commission_rate or self._commission_rate
        slip = slippage_rate or self._slippage_rate

        plan = CostOptimizedPlan(portfolio_id=portfolio_id)

        for trade_data in trades:
            asset = trade_data.get("asset", "")
            action = trade_data.get("action", "buy")
            trade_size_pct = abs(trade_data.get("weight_diff", 0.0))
            trade_value = trade_size_pct * capital

            # Commission
            commission = max(trade_value * comm, self._min_commission)

            # Slippage
            slippage = trade_value * slip

            # Market impact (Almgren-Chriss square-root model)
            if adv_data and asset in adv_data:
                adv = adv_data[asset]
                participation = trade_value / max(adv, 1.0)
                market_impact = (
                    trade_value * self._impact_factor * (participation ** 0.5)
                )
            else:
                market_impact = trade_value * slip * 0.5

            total_cost = commission + slippage + market_impact
            cost_bps = (total_cost / capital) * 10000 if capital > 0 else 0

            cost_trade = CostTrade(
                asset=asset,
                trade_size=trade_size_pct,
                action=action,
                commission=commission,
                slippage=slippage,
                market_impact=market_impact,
                total_cost=total_cost,
                cost_bps=cost_bps,
            )

            plan.trades.append(cost_trade)
            plan.total_commission += commission
            plan.total_slippage += slippage
            plan.total_market_impact += market_impact
            plan.total_cost += total_cost

        if capital > 0:
            plan.total_cost_bps = (plan.total_cost / capital) * 10000

        plan.metadata = {
            "capital": capital,
            "commission_rate": comm,
            "slippage_rate": slip,
            "impact_factor": self._impact_factor,
        }

        # Sort by cost descending to identify expensive trades
        plan.trades.sort(key=lambda t: t.total_cost, reverse=True)

        return plan
