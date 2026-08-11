"""Marginal Cost — computes the marginal cost of deploying additional capital.

Marginal cost includes:
- Transaction cost (commission + spread)
- Market impact cost
- Slippage cost
- Liquidity cost
- Opportunity cost of capital lock-up
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class MarginalCostResult:
    """Marginal cost analysis result."""
    strategy_id: str
    marginal_cost: float = 0.0  # in return-equivalent terms
    transaction_cost_bps: float = 0.0
    impact_cost_bps: float = 0.0
    slippage_cost_bps: float = 0.0
    liquidity_cost_bps: float = 0.0
    opportunity_cost: float = 0.0
    total_cost_bps: float = 0.0
    cost_efficiency: float = 0.0  # alpha per unit cost
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def summarize(self) -> str:
        return (
            f"MarginalCost[{self.strategy_id}] total={self.total_cost_bps:.1f}bps "
            f"txn={self.transaction_cost_bps:.1f} impact={self.impact_cost_bps:.1f} "
            f"slippage={self.slippage_cost_bps:.1f}"
        )


class MarginalCost:
    """Computes marginal cost of deploying additional capital.

    Total Marginal Cost = TxnCost + Impact + Slippage + Liquidity + Opportunity
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._commission_bps = self._config.get("commission_bps", 1.0)
        self._spread_bps = self._config.get("spread_bps", 5.0)
        self._impact_factor = self._config.get("impact_factor", 1.0)
        self._slippage_factor = self._config.get("slippage_factor", 0.5)
        self._opportunity_rate = self._config.get("opportunity_rate", 0.02)

    def compute(self, strategy_id: str,
                order_size: float = 0.0,
                daily_volume: float = 0.0,
                volatility: float = 0.0,
                bid_ask_spread_bps: Optional[float] = None,
                commission_bps: Optional[float] = None) -> MarginalCostResult:
        """Compute marginal cost of deploying capital.

        Uses square-root impact: Impact = σ * (Q/V)^0.5
        """
        spread_bps = bid_ask_spread_bps if bid_ask_spread_bps is not None else self._spread_bps
        comm_bps = commission_bps if commission_bps is not None else self._commission_bps

        # Transaction cost = commission + half-spread
        txn_cost = comm_bps + spread_bps / 2.0

        # Impact cost from square-root model
        if daily_volume > 0 and volatility > 0:
            participation = order_size / daily_volume
            impact = volatility * 10000 * self._impact_factor * (participation ** 0.5)
        else:
            impact = 0.0

        # Slippage proportional to volatility
        slippage = volatility * 10000 * self._slippage_factor

        # Liquidity cost — tier-based
        if daily_volume > 0:
            participation_pct = order_size / daily_volume
            if participation_pct < 0.01:
                liquidity_cost = 1.0
            elif participation_pct < 0.05:
                liquidity_cost = 3.0
            elif participation_pct < 0.10:
                liquidity_cost = 8.0
            else:
                liquidity_cost = 20.0
        else:
            liquidity_cost = 10.0

        total_cost_bps = txn_cost + impact + slippage + liquidity_cost

        # Opportunity cost (capital locked up)
        opportunity_cost = self._opportunity_rate * (order_size / max(1, daily_volume)) if daily_volume > 0 else 0.0

        # Convert total bps to return-equivalent
        marginal_cost = total_cost_bps / 10000.0 + opportunity_cost

        # Cost efficiency = 1 / total_cost_bps, normalized
        cost_efficiency = 1.0 / max(0.1, total_cost_bps / 100.0)

        return MarginalCostResult(
            strategy_id=strategy_id,
            marginal_cost=marginal_cost,
            transaction_cost_bps=txn_cost,
            impact_cost_bps=impact,
            slippage_cost_bps=slippage,
            liquidity_cost_bps=liquidity_cost,
            opportunity_cost=opportunity_cost,
            total_cost_bps=total_cost_bps,
            cost_efficiency=cost_efficiency,
        )

    def compute_batch(self, orders: List[Dict[str, Any]]) -> List[MarginalCostResult]:
        """Compute marginal cost for multiple orders."""
        results = []
        for o in orders:
            results.append(self.compute(
                strategy_id=o.get("strategy_id", ""),
                order_size=o.get("order_size", 0.0),
                daily_volume=o.get("daily_volume", 0.0),
                volatility=o.get("volatility", 0.0),
                bid_ask_spread_bps=o.get("bid_ask_spread_bps"),
                commission_bps=o.get("commission_bps"),
            ))
        return results
