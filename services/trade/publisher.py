from services.eventbus import (
    Event,
    EventType
)


class TradeEventPublisher:
    def __init__(self, publisher):
        self.publisher = publisher

    def publish_trade(self, trade):
        event = Event(
            "TRADE_EVENT_" + trade.trade_id,
            EventType.TRADE_EXECUTED,
            {
                "trade_id": trade.trade_id,
                "symbol": trade.symbol,
                "quantity": trade.quantity
            }
        )

        self.publisher.publish(event)