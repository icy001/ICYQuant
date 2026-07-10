from services.contracts.dto import TradeDTO

from ..event import LedgerEvent
from ..event_type import LedgerEventType


class TradeToLedger:
    def convert(self, trade: TradeDTO) -> LedgerEvent:
        cash_change = -trade.price * trade.quantity
        return LedgerEvent(
            event_type=LedgerEventType.ORDER_FILLED,
            aggregate_id=trade.user_id,
            payload={
                "user_id": trade.user_id,
                "order_id": trade.trade_id,
                "symbol": trade.symbol,
                "side": "BUY",
                "quantity": trade.quantity,
                "price": trade.price,
                "cash_change": cash_change,
                "trade_id": trade.trade_id,
            },
        )