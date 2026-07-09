from typing import Any, List

from .models import StoredEvent


class EventRepository:
    def __init__(self) -> None:
        self.events: List[StoredEvent] = []

    def append(self, event: Any) -> None:
        self.events.append(event)

    def get_all(self) -> List[StoredEvent]:
        return self.events
