"""
Alpha calculator.
"""


class AlphaCalculator:
    def calculate(
        self,
        strategy_return,
        benchmark_return,
    ):
        return strategy_return - benchmark_return