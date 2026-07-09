from typing import Callable, Union

from services.contracts.events import Event, EventType


class EventSubscriber:
    def __init__(self, publisher: "EventPublisher") -> None:
        self.publisher = publisher

    def register_handler(self, event_type: Union[EventType, str], handler: Callable[[Event], None]) -> None:
        self.publisher.subscribe(event_type, handler)
