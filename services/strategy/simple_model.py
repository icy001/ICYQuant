from dataclasses import dataclass


@dataclass
class SimpleStrategy:
    strategy_id: str
    name: str
    version: str
    description: str