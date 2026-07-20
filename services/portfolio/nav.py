"""
Portfolio NAV calculator.
"""

from decimal import Decimal


class NAVCalculator:
    def calculate(
        self,
        valuations,
        cash: Decimal,
    ):
        market_value = sum(item.market_value for item in valuations)
        return market_value + cash