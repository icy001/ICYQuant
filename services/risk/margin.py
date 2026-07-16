"""
Margin calculator.
"""

from __future__ import annotations

from decimal import Decimal

from .model import RiskRequest


class MarginCalculator:
    def calculate_required_margin(
        self,
        request: RiskRequest,
        margin_rate: Decimal,
    ) -> Decimal:
        notional = (
            request.quantity
            *
            request.price
        )

        return notional * margin_rate