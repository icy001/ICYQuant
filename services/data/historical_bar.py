"""
Historical OHLCV bar model.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class HistoricalBar:

    symbol: str

    timestamp: datetime

    open: float

    high: float

    low: float

    close: float

    volume: float