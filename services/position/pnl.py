from dataclasses import dataclass


@dataclass
class UnrealizedPnL:

    position_id: str

    market_price: float

    pnl: float