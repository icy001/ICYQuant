from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from services.common.event_bus import EventBus
from services.common.events.order_event import Event, EventType
from services.common.models import Order


def _dump_model(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


class OMS:
    def __init__(self, event_bus: EventBus) -> None:
        self.bus = event_bus

    def create_order(self, order: Order) -> Event:
        event = Event(
            event_id=str(uuid4()),
            event_type=EventType.ORDER_CREATED,
            order_id=order.order_id,
            timestamp=datetime.utcnow(),
            payload=_dump_model(order),
        )
        self.bus.publish(event)
        return event
