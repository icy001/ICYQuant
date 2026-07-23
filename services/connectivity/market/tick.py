"""
Market tick model.
"""

from dataclasses import dataclass


@dataclass
class MarketTick:

    symbol: str

    price: float

    volume: float

    timestamp: int