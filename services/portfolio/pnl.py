"""
PnL calculator.
"""

from __future__ import annotations

from decimal import Decimal


class PnLCalculator:
    def unrealized(
        self,
        cost_value: Decimal,
        market_value: Decimal,
    ) -> Decimal:
        return market_value - cost_value

    def realized(
        self,
        realized_pnl: Decimal,
    ) -> Decimal:
        return realized_pnl

    def total(
        self,
        unrealized: Decimal,
        realized: Decimal,
    ) -> Decimal:
        return unrealized + realized