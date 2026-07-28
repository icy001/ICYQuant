from dataclasses import dataclass


@dataclass
class EventRecord:
    event_id: str
    event_type: str
    payload: dict
    timestamp: int