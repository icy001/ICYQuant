"""
Sharpe ratio calculator.
"""


class SharpeRatioCalculator:

    def calculate(
        self,
        mean_return,
        volatility,
    ):

        if volatility == 0:

            return 0.0

        return mean_return / volatility