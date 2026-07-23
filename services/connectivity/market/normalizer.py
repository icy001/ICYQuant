"""
Market data normalization.
"""


class MarketDataNormalizer:

    def normalize(
        self,
        raw,
    ):
        return {
            "symbol":
                raw.symbol,
            "price":
                raw.price,
            "volume":
                raw.volume
        }