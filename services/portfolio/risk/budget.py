"""
Risk Budget Engine

Manages risk allocation across strategies:
- Single strategy risk limits (max weight, max drawdown)
- Factor exposure limits
- Risk budget computation and validation
- Risk utilization tracking
"""

from __future__ import annotations

import math
from typing import Dict, List, Optional, Tuple

from ..construction.models import (
    RiskBudget,
    RiskBudgetAllocation,
    RiskConstraint,
    StrategySnapshot,
)


class RiskBudgetManager:
    """Manages risk budgets across a portfolio."""

    def __init__(self, total_risk_budget: float = 1.0):
        self.total_risk_budget = total_risk_budget

    def allocate(
        self,
        strategies: Dict[str, StrategySnapshot],
        constraints: Optional[Dict[str, RiskConstraint]] = None,
        method: str = "equal_risk",
    ) -> Dict[str, RiskBudgetAllocation]:
        """
        Allocate risk budget across strategies.

        Methods:
        - equal_risk: Equal risk contribution per strategy
        - vol_weighted: Budget proportional to inverse volatility
        - custom: Based on explicit risk constraints
        """
        n = len(strategies)
        if n == 0:
            return {}

        if method == "vol_weighted":
            return self._allocate_vol_weighted(strategies, constraints)
        elif method == "equal_risk":
            return self._allocate_equal_risk(strategies, constraints)
        else:
            return self._allocate_custom(strategies, constraints)

    def _allocate_equal_risk(
        self,
        strategies: Dict[str, StrategySnapshot],
        constraints: Optional[Dict[str, RiskConstraint]] = None,
    ) -> Dict[str, RiskBudgetAllocation]:
        """Equal risk contribution per strategy."""
        n = len(strategies)
        budget_per = self.total_risk_budget / n
        result = {}

        for sid, snap in strategies.items():
            risk_used = snap.expected_volatility if snap.expected_volatility > 0 else budget_per

            # Apply risk constraint if present
            if constraints and sid in constraints:
                rc = constraints[sid]
                if rc.max_risk_contribution < float("inf"):
                    budget_per = min(budget_per, rc.max_risk_contribution)

            result[sid] = RiskBudgetAllocation(
                strategy_id=sid,
                risk_budget=budget_per,
                risk_used=min(risk_used, budget_per),
                risk_remaining=max(0.0, budget_per - min(risk_used, budget_per)),
                marginal_risk=snap.expected_volatility,
                percentage_of_total=budget_per / max(self.total_risk_budget, 1e-12),
            )

        return result

    def _allocate_vol_weighted(
        self,
        strategies: Dict[str, StrategySnapshot],
        constraints: Optional[Dict[str, RiskConstraint]] = None,
    ) -> Dict[str, RiskBudgetAllocation]:
        """Risk budget proportional to inverse volatility (lower vol gets more budget)."""
        inv_vols = {}
        for sid, snap in strategies.items():
            vol = snap.expected_volatility
            inv_vols[sid] = 1.0 / max(vol, 0.001)

        total_inv = sum(inv_vols.values())
        result = {}

        for sid, snap in strategies.items():
            budget = self.total_risk_budget * (inv_vols[sid] / max(total_inv, 1e-12))
            risk_used = snap.expected_volatility

            if constraints and sid in constraints:
                rc = constraints[sid]
                budget = min(budget, rc.max_risk_contribution)

            result[sid] = RiskBudgetAllocation(
                strategy_id=sid,
                risk_budget=budget,
                risk_used=min(risk_used, budget),
                risk_remaining=max(0.0, budget - min(risk_used, budget)),
                marginal_risk=snap.expected_volatility,
                percentage_of_total=budget / max(self.total_risk_budget, 1e-12),
            )

        return result

    def _allocate_custom(
        self,
        strategies: Dict[str, StrategySnapshot],
        constraints: Optional[Dict[str, RiskConstraint]] = None,
    ) -> Dict[str, RiskBudgetAllocation]:
        """Custom allocation based on explicit risk constraints."""
        result = {}
        n = len(strategies)

        for sid, snap in strategies.items():
            budget = self.total_risk_budget / n

            if constraints and sid in constraints:
                rc = constraints[sid]
                if rc.max_risk_contribution < float("inf"):
                    budget = min(budget, rc.max_risk_contribution)

            risk_used = snap.expected_volatility
            result[sid] = RiskBudgetAllocation(
                strategy_id=sid,
                risk_budget=budget,
                risk_used=min(risk_used, budget),
                risk_remaining=max(0.0, budget - min(risk_used, budget)),
                marginal_risk=snap.expected_volatility,
                percentage_of_total=budget / max(self.total_risk_budget, 1e-12),
            )

        return result

    def validate(
        self,
        allocations: Dict[str, RiskBudgetAllocation],
        snapshots: Dict[str, StrategySnapshot],
        constraints: Optional[Dict[str, RiskConstraint]] = None,
    ) -> List[str]:
        """Validate risk budget allocations. Returns list of violations."""
        violations = []

        for sid, alloc in allocations.items():
            snap = snapshots.get(sid)
            if snap is None:
                continue

            if alloc.risk_used > alloc.risk_budget:
                violations.append(
                    f"Strategy {sid}: risk used ({alloc.risk_used:.4f}) exceeds budget ({alloc.risk_budget:.4f})"
                )

            if constraints and sid in constraints:
                rc = constraints[sid]
                if snap.expected_volatility > rc.max_volatility:
                    violations.append(
                        f"Strategy {sid}: volatility ({snap.expected_volatility:.4f}) exceeds max ({rc.max_volatility})"
                    )
                if snap.max_drawdown > rc.max_drawdown:
                    violations.append(
                        f"Strategy {sid}: drawdown ({snap.max_drawdown:.4f}) exceeds max ({rc.max_drawdown})"
                    )

        return violations

    def get_utilization(
        self,
        allocations: Dict[str, RiskBudgetAllocation],
    ) -> Dict[str, float]:
        """Get risk budget utilization ratios."""
        return {
            sid: alloc.risk_used / max(alloc.risk_budget, 1e-12)
            for sid, alloc in allocations.items()
        }

    def get_total_utilization(
        self,
        allocations: Dict[str, RiskBudgetAllocation],
    ) -> float:
        """Get total risk budget utilization."""
        total_used = sum(a.risk_used for a in allocations.values())
        return total_used / max(self.total_risk_budget, 1e-12)
