"""
Real-time tick model.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Tick:

    symbol: str

    bid: float

    ask: float

    last: float

    volume: float

    timestamp: datetime