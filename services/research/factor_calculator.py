"""
Factor calculator.
"""


class FactorCalculator:

    def calculate(
        self,
        factor,
        dataset,
    ):

        return {
            "factor":
                factor.name,
            "values":
                dataset,
        }