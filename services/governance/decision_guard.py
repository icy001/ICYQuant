"""
Decision Guard — final gate before execution of any governance-cleared decision.

Ensures that even after policy/authority/constraint/approval all pass,
a final sanity check validates the decision is safe to execute.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .decision_context import DecisionContext
from .decision_request import DecisionRequest


class DecisionGuard:
    """
    Final safety gate.
    Can block decisions that passed all individual checks but are still unsafe.
    """

    def __init__(
        self,
        min_survival_score: float = 40.0,
        min_liquidity_score: float = 30.0,
        max_post_decision_risk_ratio: float = 1.0,
        strict_mode: bool = False,
    ):
        self.min_survival_score = min_survival_score
        self.min_liquidity_score = min_liquidity_score
        self.max_post_decision_risk_ratio = max_post_decision_risk_ratio
        self.strict_mode = strict_mode

    def check(
        self,
        request: DecisionRequest,
        context: DecisionContext,
        governance_evaluation: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """
        Final sanity check. Returns {"pass": bool, "reason": str}.

        This is the last line of defense — it should block only when
        executing the decision would cause immediate, clear harm.
        """
        failures = []

        # 1. Absolute survival floor — if below this, nothing risk-increasing should execute
        if context.survival_score < self.min_survival_score:
            if request.is_risk_increasing:
                failures.append(
                    f"Survival score {context.survival_score:.0f} below absolute floor "
                    f"{self.min_survival_score:.0f}"
                )

        # 2. Absolute liquidity floor
        if context.liquidity_score < self.min_liquidity_score:
            if request.is_risk_increasing:
                failures.append(
                    f"Liquidity score {context.liquidity_score:.0f} below absolute floor "
                    f"{self.min_liquidity_score:.0f}"
                )

        # 3. Post-decision risk budget check
        if context.risk_budget_total > 0 and request.post_decision_risk is not None:
            post_ratio = request.post_decision_risk / context.risk_budget_total
            if post_ratio > self.max_post_decision_risk_ratio:
                failures.append(
                    f"Post-decision risk ratio {post_ratio:.1%} exceeds guard limit "
                    f"{self.max_post_decision_risk_ratio:.1%}"
                )

        # 4. Emergency mode — block all risk-increasing
        if context.emergency_mode and request.is_risk_increasing:
            failures.append("Emergency mode active — risk-increasing decisions blocked")

        # 5. Negative available capital
        if request.requested_amount and context.available_capital > 0:
            post_available = context.available_capital - request.requested_amount
            if post_available < 0:
                failures.append(
                    f"Post-decision available capital would be negative ({post_available:,.0f})"
                )

        if failures:
            return {
                "pass": False,
                "reason": "; ".join(failures),
                "failures": failures,
            }

        return {"pass": True, "reason": "Guard passed"}

    def check_simple(self, context: DecisionContext, is_risk_increasing: bool = False) -> bool:
        """Simplified check without a full request."""
        if context.survival_score < self.min_survival_score and is_risk_increasing:
            return False
        if context.liquidity_score < self.min_liquidity_score and is_risk_increasing:
            return False
        if context.emergency_mode and is_risk_increasing:
            return False
        return True
