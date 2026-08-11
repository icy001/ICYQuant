"""Capacity Score — scores strategy capacity efficiency for allocation.

Evaluates how efficiently a strategy uses its available capacity:
- Capacity utilization level
- Remaining headroom
- Alpha decay rate
- Binding constraint identification
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class CapacityScoreResult:
    """Capacity scoring result for a strategy."""
    strategy_id: str
    score: float = 0.0  # 0-1, higher = more capacity efficient
    max_capacity: float = 0.0
    current_utilization: float = 0.0
    remaining_headroom: float = 0.0
    utilization_pct: float = 0.0
    alpha_decay_rate: float = 0.0  # How fast alpha decays with more capital
    binding_constraint: str = ""
    capacity_efficiency: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def summarize(self) -> str:
        return (
            f"CapacityScore[{self.strategy_id}] score={self.score:.3f} "
            f"util={self.utilization_pct:.1%} headroom={self.remaining_headroom:,.0f} "
            f"decay={self.alpha_decay_rate:.3f}"
        )


class CapacityScorer:
    """Scores strategies based on capacity efficiency for allocation.

    Higher score = more room to deploy capital without destroying alpha.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._utilization_weight = self._config.get("utilization_weight", 0.35)
        self._headroom_weight = self._config.get("headroom_weight", 0.30)
        self._decay_weight = self._config.get("decay_weight", 0.20)
        self._efficiency_weight = self._config.get("efficiency_weight", 0.15)

    def score(self, strategy_id: str,
              max_capacity: float = 0.0,
              current_capital: float = 0.0,
              alpha_decay_rate: float = 0.0,
              capacity_efficiency: float = 0.5,
              binding_constraint: str = "") -> CapacityScoreResult:
        """Compute capacity score for a strategy."""
        if max_capacity <= 0:
            return CapacityScoreResult(
                strategy_id=strategy_id,
                score=0.0,
                max_capacity=0.0,
                current_utilization=current_capital,
                remaining_headroom=0.0,
                utilization_pct=1.0,
            )

        utilization_pct = min(1.0, current_capital / max_capacity)
        remaining_headroom = max(0.0, max_capacity - current_capital)
        headroom_ratio = remaining_headroom / max_capacity

        # Utilization component: lower is better
        util_score = 1.0 - utilization_pct

        # Headroom component: more headroom is better
        headroom_score = headroom_ratio

        # Decay component: slower decay is better
        decay_score = max(0.0, 1.0 - alpha_decay_rate / 0.5)

        score = (
            self._utilization_weight * util_score +
            self._headroom_weight * headroom_score +
            self._decay_weight * decay_score +
            self._efficiency_weight * capacity_efficiency
        )

        return CapacityScoreResult(
            strategy_id=strategy_id,
            score=max(0.0, min(1.0, score)),
            max_capacity=max_capacity,
            current_utilization=current_capital,
            remaining_headroom=remaining_headroom,
            utilization_pct=utilization_pct,
            alpha_decay_rate=alpha_decay_rate,
            binding_constraint=binding_constraint,
            capacity_efficiency=capacity_efficiency,
        )

    def score_from_curve(self, strategy_id: str,
                         base_capital: float,
                         base_return: float,
                         decay_exponent: float,
                         current_capital: float,
                         max_capacity: float) -> CapacityScoreResult:
        """Compute capacity score from alpha decay curve parameters.

        Return = BaseReturn * (BaseCapital / Capital)^decay_exponent
        """
        alpha_decay_rate = decay_exponent * (current_capital / base_capital) if base_capital > 0 else 0.0

        # Capacity efficiency from remaining return ratio
        if current_capital > 0 and base_capital > 0:
            ratio = base_capital / current_capital
            capacity_efficiency = ratio ** decay_exponent
        else:
            capacity_efficiency = 1.0

        return self.score(
            strategy_id=strategy_id,
            max_capacity=max_capacity,
            current_capital=current_capital,
            alpha_decay_rate=min(1.0, alpha_decay_rate),
            capacity_efficiency=min(1.0, capacity_efficiency),
        )

    def batch_score(self, strategies: Dict[str, Dict[str, Any]]) -> List[CapacityScoreResult]:
        """Score multiple strategies at once."""
        results = []
        for sid, params in strategies.items():
            if all(k in params for k in ("base_capital", "base_return", "decay_exponent")):
                result = self.score_from_curve(strategy_id=sid, **params)
            else:
                result = self.score(strategy_id=sid, **params)
            results.append(result)
        return results
