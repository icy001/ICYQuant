"""
PnL calculator.
"""

from decimal import Decimal


class PnLCalculator:
    def unrealized(
        self,
        quantity: Decimal,
        cost: Decimal,
        price: Decimal,
    ):
        return (price - cost) * quantity