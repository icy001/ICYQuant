"""Marginal Capacity — computes marginal capacity efficiency.

Marginal capacity answers: "How much more capital can this strategy
absorb before alpha fully decays?"

Computes Risk-Adjusted Marginal Capital Efficiency:
    RAMCE = MarginalAlpha / (MarginalRisk + MarginalCost)
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class MarginalCapacityResult:
    """Marginal capacity analysis result."""
    strategy_id: str
    marginal_capacity: float = 0.0  # additional capital that can be absorbed
    remaining_capacity: float = 0.0
    max_capacity: float = 0.0
    current_utilization: float = 0.0
    marginal_alpha: float = 0.0
    marginal_risk: float = 0.0
    marginal_cost: float = 0.0
    risk_adjusted_mce: float = 0.0  # RAMCE = MarginalAlpha / (MarginalRisk + MarginalCost)
    binding_constraint: str = ""
    utilization_pct: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def summarize(self) -> str:
        return (
            f"MarginalCapacity[{self.strategy_id}] "
            f"remaining={self.remaining_capacity:,.0f}/{self.max_capacity:,.0f} "
            f"RAMCE={self.risk_adjusted_mce:.4f} util={self.utilization_pct:.1%}"
        )


class MarginalCapacity:
    """Computes marginal capacity and Risk-Adjusted MCE.

    RAMCE = MarginalAlpha / (MarginalRisk + MarginalCost)

    This is the key metric for prioritizing where new capital goes:
    the strategy with the highest RAMCE gets capital first.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self._config = config or {}
        self._min_marginal_alpha = self._config.get("min_marginal_alpha", 0.02)
        self._cost_base_bps = self._config.get("cost_base_bps", 5.0)

    def compute(self, strategy_id: str,
                marginal_alpha: float = 0.0,
                marginal_risk: float = 0.0,
                marginal_cost: float = 0.0,
                max_capacity: float = 0.0,
                current_capital: float = 0.0) -> MarginalCapacityResult:
        """Compute marginal capacity and RAMCE."""
        remaining = max(0.0, max_capacity - current_capital)
        utilization_pct = current_capital / max_capacity if max_capacity > 0 else 1.0

        # Risk-adjusted marginal capital efficiency
        denominator = marginal_risk + marginal_cost
        if denominator <= 0:
            rams = marginal_alpha
        else:
            rams = marginal_alpha / denominator

        # Binding constraint identification
        binding = ""
        if utilization_pct > 0.95:
            binding = "capacity"
        elif marginal_risk > 0.05:
            binding = "risk"
        elif marginal_cost > 0.03:
            binding = "cost"

        return MarginalCapacityResult(
            strategy_id=strategy_id,
            marginal_capacity=remaining,
            remaining_capacity=remaining,
            max_capacity=max_capacity,
            current_utilization=current_capital,
            marginal_alpha=marginal_alpha,
            marginal_risk=marginal_risk,
            marginal_cost=marginal_cost,
            risk_adjusted_mce=max(0.0, rams),
            binding_constraint=binding,
            utilization_pct=utilization_pct,
        )

    def compute_batch(self, strategies: List[Dict[str, Any]],
                      marginal_alphas: Optional[Dict[str, float]] = None,
                      marginal_risks: Optional[Dict[str, float]] = None,
                      marginal_costs: Optional[Dict[str, float]] = None,
                      capacities: Optional[Dict[str, float]] = None,
                      current_capitals: Optional[Dict[str, float]] = None
                      ) -> List[MarginalCapacityResult]:
        """Compute marginal capacity for multiple strategies."""
        marginal_alphas = marginal_alphas or {}
        marginal_risks = marginal_risks or {}
        marginal_costs = marginal_costs or {}
        capacities = capacities or {}
        current_capitals = current_capitals or {}

        results = []
        for s in strategies:
            sid = s.get("strategy_id", "")
            results.append(self.compute(
                strategy_id=sid,
                marginal_alpha=marginal_alphas.get(sid, s.get("marginal_alpha", 0.0)),
                marginal_risk=marginal_risks.get(sid, s.get("marginal_risk", 0.0)),
                marginal_cost=marginal_costs.get(sid, s.get("marginal_cost", 0.0)),
                max_capacity=capacities.get(sid, s.get("max_capacity", 0.0)),
                current_capital=current_capitals.get(sid, s.get("current_capital", 0.0)),
            ))
        return results

    def rank_by_rams(self, results: List[MarginalCapacityResult]) -> List[MarginalCapacityResult]:
        """Rank strategies by Risk-Adjusted MCE descending."""
        return sorted(results, key=lambda r: r.risk_adjusted_mce, reverse=True)

    def allocate_incremental(self, results: List[MarginalCapacityResult],
                              incremental_capital: float) -> Dict[str, float]:
        """Allocate incremental capital to highest RAMCE strategies first."""
        ranked = self.rank_by_rams(results)
        allocations = {}
        remaining = incremental_capital

        for r in ranked:
            if remaining <= 0:
                break
            alloc = min(remaining, r.remaining_capacity)
            allocations[r.strategy_id] = alloc
            remaining -= alloc

        return allocations
