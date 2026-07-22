"""
Unified Data API.
"""


class UnifiedDataAPI:

    def __init__(
        self,
        platform,
    ):

        self.platform = platform

    def market(
        self,
        symbol,
    ):

        return self.platform.market_data.get_market_data(
            symbol,
        )

    def history(
        self,
        symbol,
    ):

        return self.platform.historical.sync(
            symbol,
        )

    def feature(
        self,
        entity,
        feature,
    ):

        return self.platform.feature.get(
            entity,
            feature,
        )