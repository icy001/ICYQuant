"""
Confidence interval calculator.
"""


class ConfidenceIntervalCalculator:

    def calculate(
        self,
        values,
    ):

        values = sorted(values)

        return (
            values[
                int(len(values) * 0.025)
            ],
            values[
                int(len(values) * 0.975)
            ],
        )