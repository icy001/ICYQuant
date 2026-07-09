from datetime import datetime
from typing import List

from services.contracts.events import Event


class ReplayService:
    def __init__(self) -> None:
        self.events: List[Event] = []

    def record_event(self, event: Event) -> None:
        self.events.append(event)

    def replay(
        self,
        start_time: datetime | None = None,
        end_time: datetime | None = None,
    ) -> List[Event]:
        filtered = self.events

        if start_time:
            filtered = [e for e in filtered if e.timestamp >= start_time]

        if end_time:
            filtered = [e for e in filtered if e.timestamp <= end_time]

        return sorted(filtered, key=lambda e: e.timestamp)

    def clear(self) -> None:
        self.events = []
