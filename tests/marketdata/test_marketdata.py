from services.marketdata import *

from .mock_provider import MockProvider


def test_market_data_service():

    service = MarketDataService(
        MarketDataManager(
            MockProvider(),
            MarketDataCache()
        )
    )

    quote = service.quote(
        "NVDA"
    )

    assert quote.symbol == "NVDA"