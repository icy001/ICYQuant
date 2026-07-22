"""
Historical volatility calculator.
"""


class HistoricalVolatilityCalculator:

    def calculate(
        self,
        returns,
    ):

        if not returns:

            return 0

        mean = sum(
            returns
        ) / len(
            returns
        )

        variance = sum(
            (
                r - mean
            ) ** 2
            for r in returns
        ) / len(
            returns
        )

        return variance ** 0.5