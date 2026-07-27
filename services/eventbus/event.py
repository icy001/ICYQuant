from dataclasses import dataclass

import time


@dataclass
class Event:
    event_id: str
    event_type: str
    payload: dict
    timestamp: float = time.time()