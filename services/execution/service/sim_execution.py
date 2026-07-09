from contracts.events.execution_event import ExecutionCompletedEvent, ExecutionStartedEvent
from contracts.events.trade_event import TradeEvent


class SimExecution:
    def execute(self, order):
        started_event = ExecutionStartedEvent(
            event_id=order.id,
            order_id=order.id,
            symbol=order.symbol,
        )

        trade_event = TradeEvent(
            event_id=order.id,
            symbol=order.symbol,
            side=order.side.value,
            quantity=order.quantity,
        )

        completed_event = ExecutionCompletedEvent(
            event_id=order.id,
            order_id=order.id,
            symbol=order.symbol,
            quantity=order.quantity,
            price=order.price,
            status="FILLED",
        )

        return trade_event
