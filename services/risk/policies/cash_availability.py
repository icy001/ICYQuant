"""
Cash availability policy.
"""

from __future__ import annotations

from ..context.decision_context import RiskDecisionContext
from ..decision.risk_decision import RiskDecision, RiskDecisionStatus
from .base import RiskPolicy


class CashAvailabilityPolicy(RiskPolicy):

    policy_id = "cash_availability"

    def evaluate(self, context: RiskDecisionContext) -> RiskDecision:

        required_cash = context.quantity * context.price

        if context.side != "BUY":
            return RiskDecision(
                status=RiskDecisionStatus.APPROVED,
                policy_id=self.policy_id,
                correlation_id=context.correlation_id,
                causation_id=context.causation_id,
                lineage_id=context.lineage_id,
            )

        if required_cash > context.available_cash:
            return RiskDecision(
                status=RiskDecisionStatus.REJECTED,
                reason_code="INSUFFICIENT_CASH",
                reason="available cash is insufficient",
                policy_id=self.policy_id,
                correlation_id=context.correlation_id,
                causation_id=context.causation_id,
                lineage_id=context.lineage_id,
            )

        return RiskDecision(
            status=RiskDecisionStatus.APPROVED,
            policy_id=self.policy_id,
            correlation_id=context.correlation_id,
            causation_id=context.causation_id,
            lineage_id=context.lineage_id,
        )
