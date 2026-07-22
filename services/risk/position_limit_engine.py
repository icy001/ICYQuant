"""
Position limit engine.
"""


class PositionLimitEngine:

    def __init__(
        self,
        repository,
        calculator,
        validator,
    ):

        self.repository = repository

        self.calculator = calculator

        self.validator = validator

    def check(
        self,
        symbol,
        current,
        incoming,
    ):

        limit = self.repository.load(
            symbol,
        )

        exposure = self.calculator.calculate(
            current,
            incoming,
        )

        return self.validator.validate(
            exposure,
            limit,
        )