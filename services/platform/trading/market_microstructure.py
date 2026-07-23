"""
Market microstructure intelligence.
"""


class MarketMicrostructureIntelligence:

    def analyze(
        self,
        market,
    ):

        return {
            "spread":
                market.get("spread"),
            "liquidity":
                market.get("liquidity"),
        }