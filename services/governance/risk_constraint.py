"""
Risk Constraint — enforces risk budget and risk limits.
"""

from __future__ import annotations

from .governance_constraint import GovernanceConstraint, ConstraintResult
from .decision_context import DecisionContext
from .decision_request import DecisionRequest


class RiskConstraint(GovernanceConstraint):
    """Ensures decision stays within risk budget."""

    def __init__(
        self,
        max_risk_budget_utilization: float = 1.0,
        max_var_99_ratio: float = float("inf"),
        max_es_ratio: float = float("inf"),
        blocking: bool = True,
    ):
        super().__init__(name="risk", blocking=blocking)
        self.max_risk_budget_utilization = max_risk_budget_utilization
        self.max_var_99_ratio = max_var_99_ratio
        self.max_es_ratio = max_es_ratio

    def evaluate(self, request: DecisionRequest, context: DecisionContext) -> ConstraintResult:
        # Risk budget
        if context.risk_budget_total > 0:
            # Post-decision risk
            post_risk = context.risk_budget_used
            if request.additional_risk:
                post_risk += request.additional_risk

            utilization = post_risk / context.risk_budget_total
            if utilization > self.max_risk_budget_utilization:
                return ConstraintResult.fail(
                    self.name,
                    reason=f"Post-decision risk utilization {utilization:.1%} exceeds max {self.max_risk_budget_utilization:.1%}",
                    blocking=self.blocking,
                    actual=utilization,
                    limit=self.max_risk_budget_utilization,
                )

        # VaR check
        if context.var_99 and context.capital > 0:
            var_ratio = abs(context.var_99) / context.capital
            if var_ratio > self.max_var_99_ratio:
                if request.is_risk_increasing:
                    return ConstraintResult.fail(
                        self.name,
                        reason=f"VaR 99% ratio {var_ratio:.1%} exceeds max {self.max_var_99_ratio:.1%}",
                        blocking=self.blocking,
                        actual=var_ratio,
                        limit=self.max_var_99_ratio,
                    )

        # ES check
        if context.expected_shortfall and context.capital > 0:
            es_ratio = abs(context.expected_shortfall) / context.capital
            if es_ratio > self.max_es_ratio:
                if request.is_risk_increasing:
                    return ConstraintResult.fail(
                        self.name,
                        reason=f"Expected Shortfall ratio {es_ratio:.1%} exceeds max {self.max_es_ratio:.1%}",
                        blocking=self.blocking,
                        actual=es_ratio,
                        limit=self.max_es_ratio,
                    )

        return ConstraintResult.pass_(self.name)
