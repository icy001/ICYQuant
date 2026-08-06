"""Portfolio Rebalancer — generate rebalance plans from target weights.

Supports rebalancing methods:
* Periodic — calendar-based rebalancing
* Threshold — rebalance when weight deviation exceeds threshold
* Event Driven — rebalance on specific events
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class RebalanceMethod(str, Enum):
    """Rebalancing trigger methods."""

    PERIODIC = "periodic"
    THRESHOLD = "threshold"
    EVENT_DRIVEN = "event_driven"


@dataclass
class RebalanceTrade:
    """A single trade in a rebalance plan."""

    asset: str
    current_weight: float
    target_weight: float
    weight_diff: float
    action: str  # "buy", "sell", "hold"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset": self.asset,
            "current_weight": self.current_weight,
            "target_weight": self.target_weight,
            "weight_diff": self.weight_diff,
            "action": self.action,
        }


@dataclass
class RebalancePlan:
    """Complete rebalance plan with trades and metrics."""

    portfolio_id: str
    method: RebalanceMethod
    date: str
    trades: List[RebalanceTrade] = field(default_factory=list)
    total_turnover: float = 0.0
    num_buys: int = 0
    num_sells: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "portfolio_id": self.portfolio_id,
            "method": self.method.value,
            "date": self.date,
            "trades": [t.to_dict() for t in self.trades],
            "total_turnover": self.total_turnover,
            "num_buys": self.num_buys,
            "num_sells": self.num_sells,
            "metadata": self.metadata,
        }


class Rebalancer:
    """Generate rebalance plans from target vs current weights.

    Computes weight differences and generates trade lists
    for periodic, threshold-based, or event-driven rebalancing.
    """

    def __init__(self) -> None:
        self._threshold: float = 0.02  # 2% deviation threshold

    async def generate_plan(
        self,
        portfolio_id: str,
        current_weights: Dict[str, float],
        target_weights: Dict[str, float],
        method: RebalanceMethod = RebalanceMethod.THRESHOLD,
        threshold: Optional[float] = None,
        date: Optional[str] = None,
        **kwargs: Any,
    ) -> RebalancePlan:
        """Generate a rebalance plan."""

        if date is None:
            date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

        plan = RebalancePlan(
            portfolio_id=portfolio_id,
            method=method,
            date=date,
        )

        if method == RebalanceMethod.THRESHOLD:
            plan = self._threshold_rebalance(
                plan, current_weights, target_weights,
                threshold or self._threshold,
            )
        elif method == RebalanceMethod.PERIODIC:
            plan = self._periodic_rebalance(
                plan, current_weights, target_weights,
            )
        else:
            plan = self._periodic_rebalance(
                plan, current_weights, target_weights,
            )

        # Compute turnover
        plan.total_turnover = sum(
            abs(t.weight_diff) for t in plan.trades
        ) / 2.0  # one-sided turnover

        return plan

    def _threshold_rebalance(
        self,
        plan: RebalancePlan,
        current: Dict[str, float],
        target: Dict[str, float],
        threshold: float,
    ) -> RebalancePlan:
        """Only trade assets exceeding threshold deviation."""
        all_assets = set(current.keys()) | set(target.keys())

        for asset in sorted(all_assets):
            cw = current.get(asset, 0.0)
            tw = target.get(asset, 0.0)
            diff = tw - cw

            if abs(diff) < threshold:
                continue

            if diff > 0:
                plan.trades.append(RebalanceTrade(
                    asset=asset,
                    current_weight=cw,
                    target_weight=tw,
                    weight_diff=diff,
                    action="buy",
                ))
                plan.num_buys += 1
            elif diff < 0:
                plan.trades.append(RebalanceTrade(
                    asset=asset,
                    current_weight=cw,
                    target_weight=tw,
                    weight_diff=abs(diff),
                    action="sell",
                ))
                plan.num_sells += 1

        return plan

    def _periodic_rebalance(
        self,
        plan: RebalancePlan,
        current: Dict[str, float],
        target: Dict[str, float],
    ) -> RebalancePlan:
        """Full rebalance — trade all differences."""
        all_assets = set(current.keys()) | set(target.keys())

        for asset in sorted(all_assets):
            cw = current.get(asset, 0.0)
            tw = target.get(asset, 0.0)
            diff = tw - cw

            if abs(diff) < 1e-6:
                continue

            if diff > 0:
                plan.trades.append(RebalanceTrade(
                    asset=asset, current_weight=cw,
                    target_weight=tw, weight_diff=diff, action="buy",
                ))
                plan.num_buys += 1
            else:
                plan.trades.append(RebalanceTrade(
                    asset=asset, current_weight=cw,
                    target_weight=tw, weight_diff=abs(diff), action="sell",
                ))
                plan.num_sells += 1

        return plan
