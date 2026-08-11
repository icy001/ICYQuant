"""
Leverage Constraint — enforces maximum leverage limits.
"""

from __future__ import annotations

from .governance_constraint import GovernanceConstraint, ConstraintResult
from .decision_context import DecisionContext
from .decision_request import DecisionRequest


class LeverageConstraint(GovernanceConstraint):
    """Ensures leverage stays within institutional limits."""

    def __init__(self, max_leverage: float = 3.0, blocking: bool = True):
        super().__init__(name="leverage", blocking=blocking)
        self.max_leverage = max_leverage

    def evaluate(self, request: DecisionRequest, context: DecisionContext) -> ConstraintResult:
        current = context.current_leverage
        requested = request.requested_leverage

        if requested is not None:
            if requested > self.max_leverage:
                return ConstraintResult.fail(
                    self.name,
                    reason=f"Requested leverage {requested:.1f}x exceeds max {self.max_leverage:.1f}x",
                    blocking=self.blocking,
                    actual=requested,
                    limit=self.max_leverage,
                )

        if current > self.max_leverage:
            if request.is_risk_increasing:
                return ConstraintResult.fail(
                    self.name,
                    reason=(f"Current leverage {current:.1f}x exceeds max {self.max_leverage:.1f}x "
                            "— risk-increasing decisions blocked"),
                    blocking=self.blocking,
                    actual=current,
                    limit=self.max_leverage,
                )

        return ConstraintResult.pass_(self.name)
