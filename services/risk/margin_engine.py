"""
Margin risk engine.
"""


class MarginEngine:

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
        notional,
        available_margin,
    ):

        requirement = self.repository.load(
            symbol,
        )

        required = self.calculator.calculate(
            notional,
            requirement.initial_margin_ratio,
        )

        return self.validator.validate(
            available_margin,
            required,
        )