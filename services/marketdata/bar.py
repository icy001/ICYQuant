from dataclasses import dataclass


@dataclass
class Bar:

    symbol: str

    open: float

    high: float

    low: float

    close: float

    volume: float

    timestamp: int