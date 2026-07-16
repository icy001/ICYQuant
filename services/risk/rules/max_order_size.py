"""
Maximum order size rule.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from ..context import RiskContext
from ..decision import RiskResult
from ..enums import RiskDecision
from ..model import RiskRequest


class MaxOrderSizeRule:
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
        if request.quantity > self.limit:
            return RiskResult(
                decision=RiskDecision.REJECT,
                reason="Order size exceeds limit",
            )
        return None