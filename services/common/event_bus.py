from collections import defaultdict
from typing import Callable

from services.common.events.order_event import Event, EventType

EventHandler = Callable[[Event], None]


class EventBus:
    def __init__(self) -> None:
        self.subscribers: dict[EventType, list[EventHandler]] = defaultdict(list)

    def subscribe(self, event_type: EventType | str, handler: EventHandler) -> None:
        normalized_event_type = self._normalize_event_type(event_type)
        self.subscribers[normalized_event_type].append(handler)

    def publish(self, event: Event) -> None:
        handlers = list(self.subscribers.get(event.event_type, []))
        for handler in handlers:
            handler(event)

    @staticmethod
    def _normalize_event_type(event_type: EventType | str) -> EventType:
        if isinstance(event_type, EventType):
            return event_type
        return EventType(event_type)
