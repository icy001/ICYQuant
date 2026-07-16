"""
Margin validation rule.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from ..context import RiskContext
from ..decision import RiskResult
from ..enums import RiskDecision
from ..margin import MarginCalculator
from ..model import RiskRequest


class MarginRule:
    def __init__(
        self,
        margin_rate: Decimal,
    ):
        self.margin_rate = margin_rate
        self.calculator = MarginCalculator()

    def evaluate(
        self,
        request: RiskRequest,
        context: RiskContext,
    ) -> Optional[RiskResult]:
        required = (
            self.calculator
            .calculate_required_margin(
                request,
                self.margin_rate,
            )
        )

        if required > context.account.available_margin:
            return RiskResult(
                decision=RiskDecision.REJECT,
                reason="Insufficient margin",
            )

        return None