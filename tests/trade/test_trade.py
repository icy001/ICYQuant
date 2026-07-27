from services.trade import *


def test_trade_service():
    repository = TradeRepository()

    class MockPublisher:
        def publish(self, event):
            self.event = event

    publisher = MockPublisher()

    event_publisher = TradeEventPublisher(publisher)

    manager = TradeManager(repository, event_publisher)

    service = TradeService(manager)

    trade = Trade(
        "TRD001",
        "ORD001",
        "ACC001",
        "NVDA",
        10,
        150.5,
        TradeSide.BUY,
        1000
    )

    result = service.confirm(trade)

    assert result.symbol == "NVDA"