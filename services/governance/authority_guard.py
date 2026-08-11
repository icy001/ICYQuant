"""
Authority Guard — prevents unauthorized decision execution.

Ensures that only authorized actors execute authorized decision types,
preventing cross-cutting concerns like a Strategy Runtime executing
capital allocation or an Order Engine modifying risk budgets.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .authority_engine import AuthorityEngine, AuthorityEvaluationResult
from .decision_context import DecisionContext
from .decision_request import DecisionRequest


class AuthorityGuard:
    """
    Runtime authority enforcement.
    Checks "who", "what", "scope", "amount", "authority" for every decision.
    """

    def __init__(self, authority_engine: Optional[AuthorityEngine] = None):
        self._engine = authority_engine or AuthorityEngine()
        self._violations: List[Dict[str, Any]] = []

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, request: DecisionRequest, context: DecisionContext) -> AuthorityEvaluationResult:
        """Check authority for a decision."""
        result = self._engine.evaluate(request, context)

        if not result.authorized:
            self._violations.append({
                "request_id": request.request_id,
                "actor": request.actor,
                "decision_type": request.decision_type.name,
                "reason": result.reason,
                "timestamp": request.timestamp,
            })

        return result

    def is_authorized(self, request: DecisionRequest, context: DecisionContext) -> bool:
        """Quick check."""
        return self.check(request, context).authorized

    # ------------------------------------------------------------------
    # Cross-cutting prevention
    # ------------------------------------------------------------------

    def prevent_unauthorized(self, request: DecisionRequest, context: DecisionContext) -> bool:
        """
        Stricter check: reject if actor is not in the expected set for this decision type.
        Used to prevent strategy actors from doing capital allocation, etc.
        """
        actor = request.actor.upper()
        decision_type = request.decision_type.name

        # Define who CANNOT do what
        denied_map = {
            "STRATEGY": {"CAPITAL_ALLOCATION", "CAPITAL_REBALANCE", "RISK_BUDGET_CHANGE",
                         "LEVERAGE_CHANGE", "POLICY_OVERRIDE"},
            "ORDER_ENGINE": {"RISK_BUDGET_CHANGE", "LEVERAGE_CHANGE", "POLICY_OVERRIDE",
                             "AUTHORITY_CHANGE"},
            "EXECUTION_ENGINE": {"CAPITAL_ALLOCATION", "RISK_BUDGET_CHANGE",
                                 "POLICY_OVERRIDE", "AUTHORITY_CHANGE"},
            "MARKET_DATA": {"CAPITAL_ALLOCATION", "RISK_BUDGET_CHANGE", "ORDER_SUBMIT",
                            "POLICY_OVERRIDE"},
        }

        denied = denied_map.get(actor, set())
        if decision_type in denied:
            result = AuthorityEvaluationResult(
                authorized=False,
                reason=f"Actor '{request.actor}' is not permitted to execute '{decision_type}'",
            )
            return False

        return self.check(request, context).authorized

    # ------------------------------------------------------------------
    # Violations
    # ------------------------------------------------------------------

    def get_violations(self) -> List[Dict[str, Any]]:
        return list(self._violations)

    def get_recent_violations(self, n: int = 20) -> List[Dict[str, Any]]:
        return self._violations[-n:]

    def clear_violations(self) -> None:
        self._violations.clear()
