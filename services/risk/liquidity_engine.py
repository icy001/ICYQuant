"""
Liquidity risk engine.
"""


class LiquidityEngine:

    def __init__(
        self,
        repository,
        calculator,
        impact_estimator,
        validator,
    ):

        self.repository = repository

        self.calculator = calculator

        self.impact_estimator = impact_estimator

        self.validator = validator

    def check(
        self,
        symbol,
        order_quantity,
        limit,
    ):

        profile = self.repository.load(
            symbol
        )

        volume_ratio = self.calculator.calculate_volume_ratio(
            order_quantity,
            profile.average_volume,
        )

        impact = self.impact_estimator.estimate(
            volume_ratio
        )

        return self.validator.validate(
            volume_ratio,
            impact,
            limit,
        )