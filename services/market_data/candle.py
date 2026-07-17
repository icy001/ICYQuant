"""
OHLCV candle.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime


@dataclass(frozen=True)
class Candle:
    symbol: str
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: Decimal
    timestamp: datetime