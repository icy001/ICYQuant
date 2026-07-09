from datetime import datetime
from typing import Any
from uuid import uuid4

from pydantic import BaseModel

from services.contracts.dto import OrderDTO
from services.contracts.events import Event, EventType
from services.eventbus.publisher import EventPublisher


def _dump_model(model: BaseModel) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


class OMS:
    def __init__(self, event_bus: EventPublisher) -> None:
        self.bus = event_bus

    def create_order(self, order: OrderDTO) -> Event:
        event = Event(
            event_id=str(uuid4()),
            event_type=EventType.ORDER_CREATED,
            order_id=order.order_id,
            timestamp=datetime.utcnow(),
            payload=_dump_model(order),
        )
        self.bus.publish(event)
        return event
