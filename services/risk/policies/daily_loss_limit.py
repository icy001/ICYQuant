"""
Daily loss limit policy.
"""

from __future__ import annotations

from decimal import Decimal

from ..context.decision_context import RiskDecisionContext
from ..decision.risk_decision import RiskDecision, RiskDecisionStatus
from .base import RiskPolicy


class DailyLossLimitPolicy(RiskPolicy):

    policy_id = "daily_loss_limit"

    def evaluate(self, context: RiskDecisionContext) -> RiskDecision:

        if context.daily_loss_limit <= Decimal("0"):
            return RiskDecision(
                status=RiskDecisionStatus.REJECTED,
                reason_code="INVALID_DAILY_LOSS_LIMIT",
                reason="daily loss limit must be positive",
                policy_id=self.policy_id,
                correlation_id=context.correlation_id,
                causation_id=context.causation_id,
                lineage_id=context.lineage_id,
            )

        if context.daily_pnl <= -context.daily_loss_limit:
            return RiskDecision(
                status=RiskDecisionStatus.REJECTED,
                reason_code="DAILY_LOSS_LIMIT_EXCEEDED",
                reason="daily loss limit exceeded",
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
