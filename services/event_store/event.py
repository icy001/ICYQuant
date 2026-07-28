from dataclasses import dataclass


@dataclass
class DomainEvent:
    event_id: str
    aggregate_id: str
    event_type: str
    payload: dict
