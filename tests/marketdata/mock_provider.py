from services.marketdata import *


class MockProvider(MarketDataProvider):

    def subscribe(
        self,
        symbol
    ):
        return Quote(
            symbol,
            150.1,
            150.2,
            100
        )