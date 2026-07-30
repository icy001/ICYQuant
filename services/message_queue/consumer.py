from dataclasses import dataclass


@dataclass
class Consumer:
    consumer_id: str
    topic: str
