"""
Portfolio stress calculator.
"""


class StressCalculator:

    def calculate(
        self,
        positions,
        scenario,
    ):

        result = {}

        for symbol, value in positions.items():

            result[symbol] = (
                value *
                (
                    1 + scenario.market_shock
                )
            )

        return result