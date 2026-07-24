from dataclasses import dataclass


@dataclass
class Tick:

    symbol: str

    price: float

    volume: float

    timestamp: int