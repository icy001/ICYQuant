"""
Leverage calculator.
"""


class LeverageCalculator:

    def calculate(
        self,
        exposure,
        equity,
    ):

        if equity == 0:

            return float(
                "inf"
            )

        return exposure / equity