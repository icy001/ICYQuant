"""OHLCV bar — aggregated market data.

Phase 1 only defines the model; 1-minute bar aggregation from
streaming quotes is Phase 2 scope (out of Commit 001).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from .instrument import Exchange


@dataclass(frozen=True)
class Bar:
    """OHLCV bar for an A-share fund.

    Timeframe is a string (e.g. "1m", "5m", "1d") rather than an
    enum so new timeframes can be added without changing the model.

    All prices in CNY.  Volume in shares.
    """

    symbol: str
    exchange: Exchange
    timeframe: str
    timestamp: datetime            # bar open time (UTC, tz-aware)
    open: Decimal
    high: Decimal
    low: Decimal
    close: Decimal
    volume: int = 0

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if not self.timeframe:
            raise ValueError("timeframe must not be empty")
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware (use UTC)")

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange.value,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp.isoformat(),
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "close": str(self.close),
            "volume": self.volume,
        }


__all__ = ["Bar"]
