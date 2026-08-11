"""
Turnover Controller — Transaction Cost-Aware Rebalance Gate

If rebalance benefit < transaction cost → SKIP the rebalance.

This prevents the portfolio from chasing "perfect weights" at the
expense of excessive trading costs.
"""

import uuid
import logging
from typing import Dict, Optional, Any

logger = logging.getLogger(__name__)


class TurnoverController:
    """
    Controls turnover by evaluating cost vs benefit of rebalancing.

    If cost of rebalancing exceeds expected benefit, skip the rebalance.
    Prevents "weight perfectionism" from destroying returns through costs.
    """

    def __init__(
        self,
        controller_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.controller_id = controller_id or f"tc-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._cost_per_trade = self.config.get("cost_per_trade_bps", 5)  # 5 bps default
        self._max_turnover = self.config.get("max_turnover_pct", 0.50)
        self._max_trades = self.config.get("max_trades_per_rebalance", 20)

    def evaluate(self, deltas: Dict[str, float]) -> Dict[str, Any]:
        """
        Evaluate if rebalancing is worth the cost.

        Args:
            deltas: {asset: weight_change}

        Returns: {cost, benefit, turnover, worthwhile}
        """
        turnover = sum(abs(d) for d in deltas.values())
        num_trades = sum(1 for d in deltas.values() if abs(d) > 0.0001)

        # Cost: each trade costs cost_per_trade bps
        cost_bps = num_trades * self._cost_per_trade / 10000  # Convert to decimal
        cost = cost_bps

        # Benefit: simplified as reversion benefit proportional to drift
        benefit = turnover * 0.01  # 1% benefit per unit of turnover (simplified)

        # Max turnover check
        if turnover > self._max_turnover:
            return {"cost": cost, "benefit": benefit, "turnover": turnover, "worthwhile": False, "reason": "Max turnover exceeded"}

        if num_trades > self._max_trades:
            return {"cost": cost, "benefit": benefit, "turnover": turnover, "worthwhile": False, "reason": "Max trades exceeded"}

        worthwhile = benefit > cost
        return {
            "cost": cost,
            "benefit": benefit,
            "turnover": turnover,
            "worthwhile": worthwhile,
            "num_trades": num_trades,
            "reason": "Benefit > cost" if worthwhile else "Cost exceeds benefit",
        }
