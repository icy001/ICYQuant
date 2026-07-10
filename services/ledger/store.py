from abc import ABC, abstractmethod
from typing import List, Optional

from .event import LedgerEvent


class EventStore(ABC):
    @abstractmethod
    def append(self, event: LedgerEvent) -> None:
        pass

    @abstractmethod
    def load(self, stream_id: str = "default") -> List[LedgerEvent]:
        pass

    @abstractmethod
    def replay(self) -> List[LedgerEvent]:
        pass


class InMemoryEventStore(EventStore):
    def __init__(self):
        self._events: List[LedgerEvent] = []

    def append(self, event: LedgerEvent) -> None:
        self._events.append(event)

    def load(self, stream_id: str = "default") -> List[LedgerEvent]:
        return [e for e in self._events if e.stream_id == stream_id]

    def replay(self) -> List[LedgerEvent]:
        return sorted(self._events, key=lambda e: e.timestamp)