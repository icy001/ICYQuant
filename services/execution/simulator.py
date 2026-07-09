from contracts.events.trade_event import TradeEvent
from .models import Fill


class SimExecution:
    def execute(self, order):
        fill = Fill(
            order_id=order.order_id,
            symbol=order.symbol,
            quantity=order.quantity,
            price=order.price,
        )

        trade_event = TradeEvent(
            event_id=order.order_id,
            symbol=order.symbol,
            side=order.side,
            quantity=order.quantity,
        )

        return fill