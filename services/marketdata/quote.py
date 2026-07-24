from dataclasses import dataclass


@dataclass
class Quote:

    symbol: str

    bid: float

    ask: float

    timestamp: int