"""
Initial margin calculator.
"""


class InitialMarginCalculator:

    def calculate(
        self,
        notional,
        ratio,
    ):

        return notional * ratio