"""
Return calculator.
"""

from decimal import Decimal


class ReturnCalculator:
    def calculate(
        self,
        start_value: Decimal,
        end_value: Decimal,
    ):
        if start_value == 0:
            return Decimal("0")
        return (end_value - start_value) / start_value