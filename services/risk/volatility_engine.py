"""
Volatility risk engine.
"""


class VolatilityEngine:

    def __init__(
        self,
        repository,
        validator,
    ):

        self.repository = repository

        self.validator = validator

    def check(
        self,
        symbol,
        limit,
    ):

        profile = self.repository.load(
            symbol
        )

        return self.validator.validate(
            profile.value,
            limit,
        )