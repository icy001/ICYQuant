"""
PnL attribution calculator.
"""

from decimal import Decimal


class PnLAttributionCalculator:
    def calculate(
        self,
        pnl_items,
    ):
        total = sum(pnl_items.values())
        result = {}
        for key, value in pnl_items.items():
            contribution = value / total if total != 0 else Decimal("0")
            result[key] = contribution
        return result