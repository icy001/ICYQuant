from dataclasses import dataclass


@dataclass
class EventMetadata:
    source: str
    timestamp: str
