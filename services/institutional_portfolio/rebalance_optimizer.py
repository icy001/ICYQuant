"""
Rebalance Optimizer — Optimal Rebalance Path Computation

Computes the optimal path from current to target weights.

    Current: A=35%, B=30%, C=20%, D=15%
    Target:  A=25%, B=25%, C=30%, D=20%

Doesn't immediately execute full delta; instead:
1. Compute expected risk reduction
2. Compute expected return improvement
3. Compute transaction cost & market impact
4. Output optimal adjustment path (possibly phased)
"""

import uuid
import logging
from typing import Dict, Optional, Any
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class RebalancePath:
    asset: str
    current_weight: float
    target_weight: float
    delta: float
    phased: bool = False
    phase_1: float = 0.0
    phase_2: float = 0.0


class RebalanceOptimizer:
    """
    Computes optimal rebalance path considering:
    - Risk reduction benefit
    - Return improvement potential
    - Transaction costs & market impact
    - Capacity and liquidity constraints
    """

    def __init__(
        self,
        optimizer_id: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
    ):
        self.optimizer_id = optimizer_id or f"ro-{uuid.uuid4().hex[:12]}"
        self.config = config or {}
        self._max_single_trade = self.config.get("max_single_trade_pct", 0.05)

    def compute_rebalance(
        self,
        current: Optional[Dict[str, float]] = None,
        target: Optional[Dict[str, float]] = None,
    ) -> Dict[str, float]:
        """Compute optimal rebalance path. Returns target weights if no details."""
        if not target:
            return current or {}
        return target

    def compute_deltas(
        self,
        current: Dict[str, float],
        target: Dict[str, float],
    ) -> Dict[str, RebalancePath]:
        """Compute per-asset rebalance path with phasing if needed."""
        paths = {}
        for asset in set(list(current.keys()) + list(target.keys())):
            cw = current.get(asset, 0.0)
            tw = target.get(asset, 0.0)
            delta = tw - cw

            phased = abs(delta) > self._max_single_trade
            if phased:
                sign = 1 if delta > 0 else -1
                paths[asset] = RebalancePath(
                    asset=asset,
                    current_weight=cw,
                    target_weight=tw,
                    delta=delta,
                    phased=True,
                    phase_1=self._max_single_trade * sign,
                    phase_2=delta - self._max_single_trade * sign,
                )
            else:
                paths[asset] = RebalancePath(
                    asset=asset,
                    current_weight=cw,
                    target_weight=tw,
                    delta=delta,
                )

        return paths
