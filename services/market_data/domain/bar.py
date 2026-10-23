"""OHLCV bar — aggregated market data (Commit 004).

1-minute bar aggregation from streaming quotes.  The Bar model is
the output of BarAggregator: each minute boundary produces a closed
Bar with OHLC + volume delta + turnover; the in-progress bar is
exposed with is_closed=False for live K-line rendering.
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

    All prices in CNY.  Volume in shares.  Turnover in CNY.

    is_closed: True when the bar's minute has elapsed; False while
    the bar is still accumulating (the "live" bar on the K-line).

    bar_id: human-readable identifier "{symbol}_{YYYYmmddHHMM}" used
    for deduplication and gap detection.
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
    turnover: Decimal = Decimal("0")
    is_closed: bool = False
    bar_id: str = ""

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if not self.timeframe:
            raise ValueError("timeframe must not be empty")
        if self.timestamp.tzinfo is None:
            raise ValueError("timestamp must be timezone-aware (use UTC)")
        if not self.bar_id:
            # Auto-generate bar_id from symbol + minute
            object.__setattr__(
                self, "bar_id",
                f"{self.symbol}_{self.timestamp.strftime('%Y%m%d%H%M')}",
            )

    @property
    def change(self) -> Decimal:
        """close - open."""
        return self.close - self.open

    @property
    def change_pct(self) -> Decimal:
        """(close - open) / open * 100."""
        if self.open <= 0:
            return Decimal("0")
        return ((self.close - self.open) / self.open * 100).quantize(
            Decimal("0.01")
        )

    def as_dict(self) -> dict:
        return {
            "symbol": self.symbol,
            "exchange": self.exchange.value,
            "timeframe": self.timeframe,
            "timestamp": self.timestamp.isoformat(),
            "bar_id": self.bar_id,
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "close": str(self.close),
            "volume": self.volume,
            "turnover": str(self.turnover),
            "is_closed": self.is_closed,
            "change": str(self.change),
            "change_pct": str(self.change_pct),
        }


__all__ = ["Bar"]
