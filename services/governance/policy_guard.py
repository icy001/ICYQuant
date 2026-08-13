"""
Policy Guard — pre-trade and pre-allocation policy enforcement.

Provides a lightweight check that can be called directly from allocation
and execution engines before they submit a decision to full governance.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from .policy_engine import PolicyEngine, PolicyEvaluationResult
from .policy import InstitutionalPolicy as Policy
from .decision_context import DecisionContext
from .decision_request import DecisionRequest


class PolicyGuard:
    """
    Lightweight pre-flight policy check.
    Designed to be embedded in allocation/execution engines as a fast pass/fail gate
    before submitting to the full governance pipeline.
    """

    def __init__(self, policy_engine: Optional[PolicyEngine] = None):
        self._engine = policy_engine or PolicyEngine()
        self._cache: Dict[str, PolicyEvaluationResult] = {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def check(self, request: DecisionRequest, context: DecisionContext) -> PolicyEvaluationResult:
        """Run policy check and return full result."""
        result = self._engine.evaluate(request, context)
        self._cache[request.request_id] = result
        return result

    def is_allowed(self, request: DecisionRequest, context: DecisionContext) -> bool:
        """Quick pass/fail."""
        result = self.check(request, context)
        return result.passed and not result.blocking

    def check_pre_allocation(
        self, strategy_id: str, target_weight: float, context: DecisionContext
    ) -> PolicyEvaluationResult:
        """Pre-allocation policy check for a strategy weight change."""
        from .decision_request import DecisionType

        request = DecisionRequest(
            actor="ALLOCATION_ENGINE",
            decision_type=DecisionType.CAPITAL_ALLOCATION,
            strategy_id=strategy_id,
            requested_amount=target_weight * context.capital,
            metadata={"target_weight": target_weight},
        )
        return self.check(request, context)

    def check_pre_order(
        self, strategy_id: str, order_amount: float, context: DecisionContext
    ) -> PolicyEvaluationResult:
        """Pre-order policy check."""
        from .decision_request import DecisionType

        request = DecisionRequest(
            actor="EXECUTION_ENGINE",
            decision_type=DecisionType.ORDER_SUBMIT,
            strategy_id=strategy_id,
            requested_amount=order_amount,
        )
        return self.check(request, context)

    # ------------------------------------------------------------------
    # Cache
    # ------------------------------------------------------------------

    def get_cached(self, request_id: str) -> Optional[PolicyEvaluationResult]:
        return self._cache.get(request_id)

    def clear_cache(self) -> None:
        self._cache.clear()
