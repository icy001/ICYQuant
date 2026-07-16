"""
Exposure calculation.
"""

from __future__ import annotations

from decimal import Decimal

from .context import RiskContext
from .model import RiskRequest


class ExposureCalculator:
    def projected_exposure(
        self,
        request: RiskRequest,
        context: RiskContext,
    ) -> Decimal:
        current = (
            context.current_position
            * request.price
        )

        incoming = (
            request.quantity
            * request.price
        )

        return current + incoming