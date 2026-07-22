"""
Historical replay tick.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ReplayTick:

    symbol: str

    timestamp: datetime

    open: float

    high: float

    low: float

    close: float

    volume: float