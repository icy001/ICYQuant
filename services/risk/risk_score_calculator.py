"""
Portfolio risk score calculator.
"""


class RiskScoreCalculator:

    def calculate(
        self,
        metrics,
    ):

        if not metrics:

            return 0.0

        return sum(
            metrics.values()
        ) / len(
            metrics
        )