from dataclasses import dataclass


@dataclass
class ReplayRequest:
    aggregate_id: str
    from_timestamp: int
    to_timestamp: int