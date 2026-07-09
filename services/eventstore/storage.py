from abc import ABC, abstractmethod
from typing import Any, List


class EventStorage(ABC):
    @abstractmethod
    def save(self, event: Any) -> None:
        ...

    @abstractmethod
    def load(self, event_id: str) -> Any:
        ...

    @abstractmethod
    def load_all(self) -> List[Any]:
        ...


class InMemoryEventStorage(EventStorage):
    def __init__(self) -> None:
        self._events = {}

    def save(self, event: Any) -> None:
        self._events[event.event_id] = event

    def load(self, event_id: str) -> Any:
        return self._events.get(event_id)

    def load_all(self) -> List[Any]:
        return list(self._events.values())
