from datetime import datetime
from decimal import Decimal

from services.market_data import (
    MarketGateway,
    MarketProvider,
    QuoteNormalizer,
)


class MockAdapter:
    provider = MarketProvider.MOCK.value

    async def connect(self):
        return None

    async def disconnect(self):
        return None

    def normalize(self, payload):
        return QuoteNormalizer().from_mapping(payload)


def test_gateway_normalize():
    gateway = MarketGateway(MockAdapter())

    quote = gateway.normalize(
        {
            "symbol": "AAPL",
            "bid": "200.10",
            "ask": "200.20",
            "last": "200.15",
            "timestamp": datetime.utcnow(),
        }
    )

    assert quote.symbol == "AAPL"
    assert quote.last == Decimal("200.15")


def test_normalizer_default_timestamp():
    normalizer = QuoteNormalizer()

    quote = normalizer.from_mapping(
        {
            "symbol": "MSFT",
            "bid": "378",
            "ask": "379",
            "last": "378.5",
        }
    )

    assert quote.symbol == "MSFT"
    assert quote.timestamp is not None