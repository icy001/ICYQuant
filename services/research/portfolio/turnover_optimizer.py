"""Turnover Optimizer — minimize turnover cost in rebalancing.

Transforms target weights into execution plans that minimize
turnover while staying close to the optimal portfolio.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class TurnoverTrade:
    """Optimized trade in a turnover-minimized plan."""

    asset: str
    current_weight: float
    target_weight: float
    executed_weight: float
    trade_size: float
    action: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset": self.asset,
            "current_weight": self.current_weight,
            "target_weight": self.target_weight,
            "executed_weight": self.executed_weight,
            "trade_size": self.trade_size,
            "action": self.action,
        }


@dataclass
class TurnoverPlan:
    """Turnover-optimized execution plan."""

    portfolio_id: str
    trades: List[TurnoverTrade] = field(default_factory=list)
    total_turnover: float = 0.0
    tracking_error: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "trades": [t.to_dict() for t in self.trades],
            "total_turnover": self.total_turnover,
            "tracking_error": self.tracking_error,
            "num_trades": len(self.trades),
            "metadata": self.metadata,
        }


class TurnoverOptimizer:
    """Minimize portfolio turnover in rebalancing.

    Balances the trade-off between tracking target weights
    and minimizing transaction costs from turnover.
    """

    def __init__(self) -> None:
        self._turnover_budget: float = 0.50  # max 50% one-sided
        self._trade_off_param: float = 0.5  # lambda in trade-off

    async def optimize(
        self,
        portfolio_id: str,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        turnover_budget: Optional[float] = None,
        trade_off: Optional[float] = None,
    ) -> TurnoverPlan:
        """Optimize trades to minimize turnover."""
        budget = turnover_budget or self._turnover_budget
        lam = trade_off or self._trade_off_param

        plan = TurnoverPlan(portfolio_id=portfolio_id)
        all_assets = set(current_weights.keys()) | set(target_weights.keys())

        # Compute raw trade sizes
        raw_trades: List[TurnoverTrade] = []
        for asset in sorted(all_assets):
            cw = current_weights.get(asset, 0.0)
            tw = target_weights.get(asset, 0.0)
            diff = tw - cw

            if abs(diff) < 1e-6:
                continue

            # Apply trade-off: shrink trade size by lambda
            adjusted_diff = diff * (1.0 - lam * abs(diff))
            executed = cw + adjusted_diff

            raw_trades.append(TurnoverTrade(
                asset=asset,
                current_weight=cw,
                target_weight=tw,
                executed_weight=executed,
                trade_size=abs(adjusted_diff),
                action="buy" if adjusted_diff > 0 else "sell",
            ))

        # Sort by trade size descending
        raw_trades.sort(key=lambda t: t.trade_size, reverse=True)

        # Apply turnover budget
        cumulative_turnover = 0.0
        selected: List[TurnoverTrade] = []
        for trade in raw_trades:
            if cumulative_turnover + trade.trade_size <= budget:
                cumulative_turnover += trade.trade_size
                selected.append(trade)
            else:
                # Scale the remaining trade to fit budget
                remaining = budget - cumulative_turnover
                if remaining > 0:
                    scale = remaining / trade.trade_size
                    adjusted = TurnoverTrade(
                        asset=trade.asset,
                        current_weight=trade.current_weight,
                        target_weight=trade.target_weight,
                        executed_weight=trade.current_weight
                        + (trade.executed_weight - trade.current_weight) * scale,
                        trade_size=remaining,
                        action=trade.action,
                    )
                    selected.append(adjusted)
                break

        plan.trades = selected
        plan.total_turnover = sum(t.trade_size for t in selected)

        # Compute tracking error (sum of squared deviation from target)
        final_weights = dict(current_weights)
        for t in selected:
            final_weights[t.asset] = t.executed_weight
        plan.tracking_error = sum(
            (final_weights.get(a, 0.0) - target_weights.get(a, 0.0)) ** 2
            for a in all_assets
        )

        plan.metadata = {
            "turnover_budget": budget,
            "trade_off_param": lam,
            "raw_trade_count": len(raw_trades),
            "executed_trade_count": len(selected),
        }

        return plan
