"""
Liquidity Constraint — enforces minimum liquidity for new risk.
"""

from __future__ import annotations

from .governance_constraint import GovernanceConstraint, ConstraintResult
from .decision_context import DecisionContext
from .decision_request import DecisionRequest


class LiquidityConstraint(GovernanceConstraint):
    """
    Ensures adequate liquidity before allowing risk-increasing decisions.
    Key principle: block new risk, allow risk reduction even in low liquidity.
    """

    def __init__(self, min_liquidity_score: float = 60.0, blocking: bool = True):
        super().__init__(name="liquidity", blocking=blocking)
        self.min_liquidity_score = min_liquidity_score

    def evaluate(self, request: DecisionRequest, context: DecisionContext) -> ConstraintResult:
        score = context.liquidity_score

        if score < self.min_liquidity_score:
            if request.is_risk_increasing:
                return ConstraintResult.fail(
                    self.name,
                    reason=(f"Liquidity score {score:.0f} below minimum {self.min_liquidity_score:.0f} "
                            "— new risk blocked"),
                    blocking=self.blocking,
                    actual=score,
                    limit=self.min_liquidity_score,
                )
            else:
                # Allow risk-reducing actions even with low liquidity
                return ConstraintResult.pass_(
                    self.name,
                    reason=f"Liquidity score {score:.0f} low but decision is risk-reducing — allowed",
                )

        return ConstraintResult.pass_(self.name)
