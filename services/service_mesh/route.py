from dataclasses import dataclass


@dataclass
class TrafficRoute:

    source: str
    target: str
    weight: int
