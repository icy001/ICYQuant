"""
Beta calculator.
"""


class BetaCalculator:
    def calculate(
        self,
        covariance,
        variance,
    ):
        if variance == 0:
            return 0
        return covariance / variance