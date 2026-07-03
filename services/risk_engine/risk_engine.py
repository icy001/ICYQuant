from datetime import datetime
from uuid import uuid4

from services.common.event_bus import EventBus
from services.common.events.order_event import Event, EventType


class RiskEngine:
    def __init__(self, bus: EventBus) -> None:
        self.bus = bus
        self.bus.subscribe(EventType.ORDER_CREATED, self.on_order_created)

    def on_order_created(self, event: Event) -> None:
        order = event.payload
        quantity = float(order.get("quantity", 0))
        approved = quantity <= 1000

        self.bus.publish(
            Event(
                event_id=str(uuid4()),
                event_type=EventType.RISK_CHECKED,
                order_id=event.order_id,
                timestamp=datetime.utcnow(),
                payload={
                    "approved": approved,
                    "reason": "Risk checks passed" if approved else "Quantity exceeds limit",
                    "order": order,
                },
            )
        )

        self.bus.publish(
            Event(
                event_id=str(uuid4()),
                event_type=EventType.ORDER_APPROVED if approved else EventType.ORDER_REJECTED,
                order_id=event.order_id,
                timestamp=datetime.utcnow(),
                payload=order,
            )
        )
