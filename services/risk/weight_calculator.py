"""
Portfolio weight calculator.
"""


class WeightCalculator:

    def calculate(
        self,
        position_value,
        portfolio_value,
    ):

        if portfolio_value == 0:

            return 0

        return (
            position_value
            /
            portfolio_value
        )