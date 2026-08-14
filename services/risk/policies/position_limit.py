"""
Position limit policy.
"""

from __future__ import annotations

from decimal import Decimal

from ..context.decision_context import RiskDecisionContext
from ..decision.risk_decision import RiskDecision, RiskDecisionStatus
from .base import RiskPolicy


class PositionLimitPolicy(RiskPolicy):

    policy_id = "position_limit"

    def evaluate(self, context: RiskDecisionContext) -> RiskDecision:

        if context.quantity <= Decimal("0"):
            return RiskDecision(
                status=RiskDecisionStatus.REJECTED,
                reason_code="INVALID_QUANTITY",
                reason="quantity must be positive",
                policy_id=self.policy_id,
                correlation_id=context.correlation_id,
                causation_id=context.causation_id,
                lineage_id=context.lineage_id,
            )

        projected_position = context.current_position

        if context.side == "BUY":
            projected_position += context.quantity
        elif context.side == "SELL":
            projected_position -= context.quantity
        else:
            return RiskDecision(
                status=RiskDecisionStatus.REJECTED,
                reason_code="INVALID_SIDE",
                reason="unsupported order side",
                policy_id=self.policy_id,
                correlation_id=context.correlation_id,
                causation_id=context.causation_id,
                lineage_id=context.lineage_id,
            )

        if abs(projected_position) > context.max_position:
            return RiskDecision(
                status=RiskDecisionStatus.REJECTED,
                reason_code="POSITION_LIMIT_EXCEEDED",
                reason="projected position exceeds limit",
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
