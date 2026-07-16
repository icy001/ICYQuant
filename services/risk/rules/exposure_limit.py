"""
Exposure limit rule.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Optional

from ..context import RiskContext
from ..decision import RiskResult
from ..enums import RiskDecision
from ..exposure import ExposureCalculator
from ..model import RiskRequest


class ExposureLimitRule:
    def __init__(
        self,
        limit: Decimal,
    ):
        self.limit = limit
        self.calculator = (
            ExposureCalculator()
        )

    def evaluate(
        self,
        request: RiskRequest,
        context: RiskContext,
    ) -> Optional[RiskResult]:
        exposure = (
            self.calculator
            .projected_exposure(
                request,
                context,
            )
        )

        if exposure > self.limit:
            return RiskResult(
                decision=RiskDecision.REJECT,
                reason="Exposure limit exceeded",
            )

        return None