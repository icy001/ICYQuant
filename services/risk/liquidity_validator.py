"""
Liquidity validator.
"""


class LiquidityValidator:

    def validate(
        self,
        volume_ratio,
        impact,
        limit,
    ):

        return (
            volume_ratio
            <=
            limit.max_volume_ratio
            and
            impact
            <=
            limit.max_market_impact
        )