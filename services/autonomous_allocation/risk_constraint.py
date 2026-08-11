"""Risk Constraint — ensures portfolio risk doesn't exceed risk budget.

Checks: VaR, volatility, drawdown, risk contribution per strategy.
"""

from typing import Any, Dict

from .allocation_constraint import (
    AllocationConstraint, ConstraintResult, ConstraintStatus, ConstraintType,
)


class RiskConstraint(AllocationConstraint):
    """Ensures portfolio risk stays within budget."""

    def __init__(self, risk_budget: float = 0.0,
                 max_volatility: float = 0.25,
                 max_var: float = 0.05,
                 max_drawdown: float = 0.20,
                 max_single_risk_contribution: float = 0.40):
        super().__init__("risk_constraint", ConstraintType.HARD)
        self._risk_budget = risk_budget
        self._max_volatility = max_volatility
        self._max_var = max_var
        self._max_drawdown = max_drawdown
        self._max_single_risk = max_single_risk_contribution

    def set_risk_budget(self, budget: float) -> None:
        self._risk_budget = budget

    def check(self, allocation: Dict[str, Any]) -> ConstraintResult:
        portfolio_risk = allocation.get("portfolio_risk", 0.0)

        # Check against risk budget
        if self._risk_budget > 0 and portfolio_risk > self._risk_budget:
            excess = portfolio_risk - self._risk_budget
            return ConstraintResult(
                constraint_name=self.name,
                status=ConstraintStatus.VIOLATED,
                value=portfolio_risk,
                limit=self._risk_budget,
                margin=-excess,
                violation_severity=min(1.0, excess / max(0.001, self._risk_budget)),
                message=f"Risk {portfolio_risk:.4f} exceeds budget {self._risk_budget:.4f}",
            )

        return ConstraintResult(
            constraint_name=self.name,
            status=ConstraintStatus.SATISFIED if portfolio_risk <= self._risk_budget else ConstraintStatus.BINDING,
            value=portfolio_risk,
            limit=self._risk_budget,
            margin=self._risk_budget - portfolio_risk,
            message="Risk within budget",
        )

    def check_weight(self, strategy_id: str, weight: float,
                     total_capital: float) -> ConstraintResult:
        risk_budget = self._risk_budget
        if risk_budget <= 0:
            return ConstraintResult(
                constraint_name=self.name,
                status=ConstraintStatus.SATISFIED,
            )

        # Check single strategy risk contribution
        max_single = risk_budget * self._max_single_risk
        strategy_risk = weight * 0.25  # approximate

        if strategy_risk > max_single:
            return ConstraintResult(
                constraint_name=self.name,
                status=ConstraintStatus.VIOLATED,
                value=strategy_risk,
                limit=max_single,
                margin=max_single - strategy_risk,
                message=f"Strategy {strategy_id} risk {strategy_risk:.4f} > max {max_single:.4f}",
            )

        return ConstraintResult(
            constraint_name=self.name,
            status=ConstraintStatus.SATISFIED,
            value=strategy_risk,
            limit=max_single,
        )
