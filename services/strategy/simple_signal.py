from dataclasses import dataclass


@dataclass
class Signal:
    strategy_id: str
    symbol: str
    action: str
    strength: float