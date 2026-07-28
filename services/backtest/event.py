from dataclasses import dataclass


@dataclass
class MarketEvent:

    symbol: str

    price: float

    timestamp: str


@dataclass
class SignalEvent:

    symbol: str

    direction: str
