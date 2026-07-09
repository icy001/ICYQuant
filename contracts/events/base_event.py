from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4


@dataclass
class BaseEvent:
    event_id: str
    timestamp: datetime

    @staticmethod
    def create() -> "BaseEvent":
        return BaseEvent(
            event_id=str(uuid4()),
            timestamp=datetime.utcnow(),
        )
