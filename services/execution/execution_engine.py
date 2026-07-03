from datetime import datetime
from uuid import uuid4

from services.common.event_bus import EventBus
from services.common.events.order_event import Event, EventType


class ExecutionEngine:
    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self.bus.subscribe(EventType.ORDER_APPROVED, self.on_approved)

    def on_approved(self, event: Event) -> None:
        order = event.payload

        self.bus.publish(
            Event(
                event_id=str(uuid4()),
                event_type=EventType.ORDER_SENT,
                order_id=event.order_id,
                timestamp=datetime.utcnow(),
                payload=order,
            )
        )

        trade_event = Event(
            event_id=str(uuid4()),
            event_type=EventType.TRADE_EXECUTED,
            order_id=event.order_id,
            timestamp=datetime.utcnow(),
            payload={
                "symbol": order.get("symbol"),
                "side": order.get("side"),
                "price": order.get("price", 100),
                "qty": order.get("quantity", 0),
            },
        )

        self.bus.publish(trade_event)
