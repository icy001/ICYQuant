"""
Leverage risk engine.
"""

from .leverage_decision import LeverageDecision


class LeverageEngine:

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
        account_id,
        exposure,
        equity,
    ):

        rule = self.repository.load(
            account_id,
        )

        leverage = self.calculator.calculate(
            exposure,
            equity,
        )

        approved = self.validator.validate(
            leverage,
            rule,
        )

        return LeverageDecision(
            approved,
            leverage,
        )