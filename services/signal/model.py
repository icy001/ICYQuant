from dataclasses import dataclass


@dataclass
class Signal:

    signal_id: str

    symbol: str

    direction: str

    score: float
