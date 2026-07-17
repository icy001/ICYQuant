"""
Portfolio monitoring service.
"""

from __future__ import annotations

from decimal import Decimal


class PortfolioMonitor:
    def get_weight(
        self,
        value: Decimal,
        equity: Decimal,
    ) -> Decimal:
        if equity == 0:
            return Decimal("0")

        return value / equity