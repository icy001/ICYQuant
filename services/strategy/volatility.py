"""
Volatility based adjustment.
"""

from __future__ import annotations

from decimal import Decimal


class VolatilityAdjuster:
    def adjust(
        self,
        base_size: Decimal,
        volatility: Decimal,
    ) -> Decimal:
        if volatility <= 0:
            return base_size

        return base_size / volatility