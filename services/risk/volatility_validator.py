"""
Volatility validator.
"""


class VolatilityValidator:

    def validate(
        self,
        volatility,
        limit,
    ):

        return (
            volatility
            <=
            limit.max_volatility
        )