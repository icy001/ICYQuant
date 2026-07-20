"""
Equity calculator.
"""


class EquityCalculator:
    def calculate(
        self,
        cash: float,
        market_value: float,
    ) -> float:
        return cash + market_value