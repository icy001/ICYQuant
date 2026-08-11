"""RiskBudgetAllocator — optimal risk budget allocation.

Allocates the capital risk budget across strategies based on
risk efficiency, expected returns, and correlation structure.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class BudgetAllocationResult:
    """Result of risk budget allocation."""

    total_budget: float = 0.0
    allocated: Dict[str, float] = field(default_factory=dict)
    remaining: float = 0.0
    efficiency_scores: Dict[str, float] = field(default_factory=dict)
    method: str = "equal"  # equal, risk_parity, efficiency_weighted


class RiskBudgetAllocator:
    """Allocates risk budget optimally across strategies.

    Methods:
    - equal: equal split
    - risk_parity: equal risk contribution
    - efficiency_weighted: weighted by risk-adjusted return efficiency
    - marginal_efficiency: weighted by marginal risk efficiency (RAMCE)

    Usage::

        allocator = RiskBudgetAllocator()
        result = allocator.allocate_efficiency_weighted(
            total_budget=8_000_000,
            strategies={"A": {"efficiency": 1.5}, "B": {"efficiency": 0.8}},
        )
    """

    def allocate_equal(
        self,
        total_budget: float,
        strategy_ids: List[str],
    ) -> BudgetAllocationResult:
        """Equal split across strategies."""
        n = len(strategy_ids)
        if n == 0:
            return BudgetAllocationResult(total_budget=total_budget)

        per_strategy = total_budget / n
        allocated = {sid: per_strategy for sid in strategy_ids}
        return BudgetAllocationResult(
            total_budget=total_budget,
            allocated=allocated,
            remaining=0.0,
            method="equal",
        )

    def allocate_efficiency_weighted(
        self,
        total_budget: float,
        strategies: Dict[str, Dict[str, float]],
        reserve_ratio: float = 0.25,
    ) -> BudgetAllocationResult:
        """Allocate by risk efficiency (risk-adjusted return per unit of risk).

        Higher efficiency → more risk budget.

        Args:
            total_budget: total risk budget
            strategies: {strategy_id: {"efficiency": float, ...}}
            reserve_ratio: fraction kept in reserve
        """
        if not strategies:
            return BudgetAllocationResult(total_budget=total_budget)

        reserve = total_budget * reserve_ratio
        allocatable = total_budget - reserve

        # get efficiency scores
        efficiencies = {
            sid: s.get("efficiency", 1.0)
            for sid, s in strategies.items()
        }
        total_eff = sum(efficiencies.values())

        allocated: Dict[str, float] = {}
        if total_eff > 0:
            for sid, eff in efficiencies.items():
                allocated[sid] = allocatable * (eff / total_eff)

        return BudgetAllocationResult(
            total_budget=total_budget,
            allocated=allocated,
            remaining=reserve,
            efficiency_scores=efficiencies,
            method="efficiency_weighted",
        )

    def allocate_risk_parity(
        self,
        total_budget: float,
        strategy_vols: Dict[str, float],
        correlations: Optional[Dict[Tuple[str, str], float]] = None,
    ) -> BudgetAllocationResult:
        """Risk parity: equal risk contribution from each strategy.

        Weight ∝ 1/σ_i (simplified; full RP requires iterative solution)
        """
        if not strategy_vols:
            return BudgetAllocationResult(total_budget=total_budget)

        inv_vols = {sid: 1.0 / max(v, 1e-9) for sid, v in strategy_vols.items()}
        total_inv = sum(inv_vols.values())

        allocated: Dict[str, float] = {}
        for sid, inv in inv_vols.items():
            allocated[sid] = total_budget * (inv / total_inv)

        return BudgetAllocationResult(
            total_budget=total_budget,
            allocated=allocated,
            remaining=0.0,
            method="risk_parity",
        )

    def allocate_marginal_efficiency(
        self,
        total_budget: float,
        marginal_efficiencies: Dict[str, float],
        reserve_ratio: float = 0.25,
    ) -> BudgetAllocationResult:
        """Allocate by marginal capital efficiency (MCE / RAMCE).

        Higher RAMCE → more budget (better use of marginal capital).
        """
        if not marginal_efficiencies:
            return BudgetAllocationResult(total_budget=total_budget)

        reserve = total_budget * reserve_ratio
        allocatable = total_budget - reserve

        # only allocate to positive MCE
        positive = {k: v for k, v in marginal_efficiencies.items() if v > 0}
        total_mce = sum(positive.values())

        allocated: Dict[str, float] = {}
        if total_mce > 0:
            for sid, mce in positive.items():
                allocated[sid] = allocatable * (mce / total_mce)

        return BudgetAllocationResult(
            total_budget=total_budget,
            allocated=allocated,
            remaining=reserve,
            efficiency_scores=marginal_efficiencies,
            method="marginal_efficiency",
        )
