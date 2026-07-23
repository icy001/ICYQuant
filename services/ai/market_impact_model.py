"""
Market impact model.
"""


class MarketImpactModel:

    def predict(
        self,
        quantity,
        liquidity,
    ):

        if liquidity == 0:

            return 1.0

        return quantity / liquidity