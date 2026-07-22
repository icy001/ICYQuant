"""
Sortino ratio calculator.
"""


class SortinoRatioCalculator:

    def calculate(
        self,
        mean_return,
        downside_deviation,
    ):

        if downside_deviation == 0:

            return 0.0

        return (
            mean_return /
            downside_deviation
        )