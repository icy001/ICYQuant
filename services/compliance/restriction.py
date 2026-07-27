from dataclasses import dataclass


@dataclass
class TradingRestriction:
    symbol: str
    restricted: bool
    reason: str