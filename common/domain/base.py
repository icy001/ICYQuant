from abc import ABC
from datetime import datetime
from typing import Optional


class DomainEvent(ABC):
    def __init__(self) -> None:
        self.timestamp: datetime = datetime.utcnow()


class Entity(ABC):
    def __init__(self, id: Optional[str] = None) -> None:
        self.id = id
