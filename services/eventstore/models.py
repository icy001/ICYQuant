from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass
class StoredEvent:
    event_id: str
    event_type: str
    data: Any
    timestamp: datetime
