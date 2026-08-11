"""
Capital Constraint — enforces capital deployment limits.
"""

from __future__ import annotations

from .governance_constraint import GovernanceConstraint, ConstraintResult
from .decision_context import DecisionContext
from .decision_request import DecisionRequest


class CapitalConstraint(GovernanceConstraint):
    """Ensures capital allocation does not exceed deployable capital."""

    def __init__(
        self,
        max_deployable: float = float("inf"),
        min_reserve: float = 0.0,
        blocking: bool = True,
    ):
        super().__init__(name="capital", blocking=blocking)
        self.max_deployable = max_deployable
        self.min_reserve = min_reserve

    def evaluate(self, request: DecisionRequest, context: DecisionContext) -> ConstraintResult:
        # Compute post-decision deployment
        requested = request.requested_amount or 0.0
        post_deployment = context.deployed_capital + requested

        if post_deployment > self.max_deployable:
            return ConstraintResult.fail(
                self.name,
                reason=f"Post-allocation capital {post_deployment:,.0f} exceeds max deployable {self.max_deployable:,.0f}",
                blocking=self.blocking,
                actual=post_deployment,
                limit=self.max_deployable,
            )

        # Check minimum reserve
        post_reserve = context.capital - post_deployment
        if post_reserve < self.min_reserve:
            return ConstraintResult.fail(
                self.name,
                reason=f"Post-allocation reserve {post_reserve:,.0f} below minimum {self.min_reserve:,.0f}",
                blocking=self.blocking,
                actual=post_reserve,
                limit=self.min_reserve,
            )

        # Check if requested amount exceeds available capital
        if requested > context.available_capital and context.available_capital > 0:
            return ConstraintResult.fail(
                self.name,
                reason=f"Requested {requested:,.0f} exceeds available capital {context.available_capital:,.0f}",
                blocking=self.blocking,
                actual=requested,
                limit=context.available_capital,
            )

        return ConstraintResult.pass_(self.name)
