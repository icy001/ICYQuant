"""
Concentration Constraint — enforces position and factor concentration limits.
"""

from __future__ import annotations

from typing import Optional

from .governance_constraint import GovernanceConstraint, ConstraintResult
from .decision_context import DecisionContext
from .decision_request import DecisionRequest


class ConcentrationConstraint(GovernanceConstraint):
    """Ensures strategy and factor concentration stay within limits."""

    def __init__(
        self,
        max_strategy_weight: float = 0.25,
        max_factor_weight: float = 0.35,
        blocking: bool = True,
    ):
        super().__init__(name="concentration", blocking=blocking)
        self.max_strategy_weight = max_strategy_weight
        self.max_factor_weight = max_factor_weight

    def evaluate(self, request: DecisionRequest, context: DecisionContext) -> ConstraintResult:
        # Strategy concentration
        strategy_id = request.strategy_id
        if strategy_id and strategy_id in context.strategy_allocations:
            current_weight = context.strategy_allocations[strategy_id]
            requested = request.requested_amount or 0.0

            if context.capital > 0:
                new_weight = (current_weight * context.capital + requested) / context.capital
                if new_weight > self.max_strategy_weight:
                    return ConstraintResult.fail(
                        self.name,
                        reason=(f"Post-allocation strategy weight {new_weight:.1%} "
                                f"exceeds max {self.max_strategy_weight:.1%}"),
                        blocking=self.blocking,
                        actual=new_weight,
                        limit=self.max_strategy_weight,
                    )

        # Factor concentration
        for factor, exposure in context.factor_concentration.items():
            if exposure > self.max_factor_weight:
                if request.is_risk_increasing:
                    return ConstraintResult.fail(
                        self.name,
                        reason=(f"Factor '{factor}' concentration {exposure:.1%} "
                                f"exceeds max {self.max_factor_weight:.1%}"),
                        blocking=self.blocking,
                        actual=exposure,
                        limit=self.max_factor_weight,
                    )

        return ConstraintResult.pass_(self.name)
