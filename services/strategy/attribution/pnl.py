"""
PnL calculation.
"""

from __future__ import annotations

from decimal import Decimal


class PnLCalculator:
    def calculate(
        self,
        entry_price: Decimal,
        exit_price: Decimal,
        quantity: Decimal,
    ) -> Decimal:
        return (exit_price - entry_price) * quantity