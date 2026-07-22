"""
Concentration risk engine.
"""


class ConcentrationEngine:

    def __init__(
        self,
        calculator,
        validator,
    ):

        self.calculator = calculator

        self.validator = validator

    def calculate(
        self,
        weights,
    ):

        return self.calculator.calculate(
            weights,
        )

    def check(
        self,
        weight,
        limit,
    ):

        return self.validator.validate(
            weight,
            limit,
        )