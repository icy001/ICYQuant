"""
Position limit rule.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from ..context import RiskContext
from ..decision import RiskResult
from ..enums import RiskDecision
from ..model import RiskRequest


class PositionLimitRule:
    def __init__(
        self,
        limit: Decimal,
    ):
        self.limit = limit

    def evaluate(
        self,
        request: RiskRequest,
        context: RiskContext,
    ) -> Optional[RiskResult]:
        projected = (
            context.current_position
            +
            request.quantity
        )

        if projected > self.limit:
            return RiskResult(
                decision=RiskDecision.REJECT,
                reason="Position limit exceeded",
            )

        return None