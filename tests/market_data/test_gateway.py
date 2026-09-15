from datetime import datetime
from decimal import Decimal

from services.market_data.gateway import MarketGateway
from services.market_data.provider import MarketProvider
from services.market_data.quote import Quote


class MockAdapter:
    provider = MarketProvider.MOCK.value

    async def connect(self):
        return None

    async def disconnect(self):
        return None

    def normalize(self, payload):
        # The original QuoteNormalizer.from_mapping was replaced by the
        # Commit 001 symbol normalizer; building the Quote directly keeps
        # the test on the gateway contract itself.
        return Quote(
            symbol=payload["symbol"],
            bid=Decimal(payload["bid"]),
            ask=Decimal(payload["ask"]),
            last=Decimal(payload["last"]),
            timestamp=payload.get("timestamp") or datetime.utcnow(),
        )


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