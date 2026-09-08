"""Unified market quote — the canonical A-share ETF/LOF quote.

Every market data adapter (mock, broker, third-party provider) must
convert its native tick into MarketQuote before pushing into ICYQuant.
This is the single contract point: downstream Strategy / Risk /
Paper Trading / Dashboard only ever see MarketQuote, never a raw
broker payload.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from .instrument import Exchange


@dataclass(frozen=True)
class MarketQuote:
    """Level-1 quote for an A-share fund.

    All prices are in CNY, using Decimal for exact tick comparison
    (A-share ETF tick size = 0.001).  Sizes are in shares (lot size
    is enforced by the instrument, not by the quote).

    Fields:
        symbol       — 6-digit code, e.g. "159852"
        exchange     — SZSE / SSE
        timestamp    — UTC datetime (exchange local time is converted)
        last         — last traded price
        bid          — best bid (limit buy)
        ask          — best ask (limit sell)
        bid_size     — total bid volume at best bid (shares)
        ask_size     — total ask volume at best ask (shares)
        volume       — cumulative volume since session open (shares)
        open         — session open price (optional, 0 if unknown)
        high         — session high (optional)
        low          — session low (optional)
        pre_close    — previous trading day close (optional)
    """

    symbol: str
    exchange: Exchange
    timestamp: datetime
    last: Decimal
    bid: Decimal
    ask: Decimal
    bid_size: int = 0
    ask_size: int = 0
    volume: int = 0
    open: Decimal = Decimal("0")
    high: Decimal = Decimal("0")
    low: Decimal = Decimal("0")
    pre_close: Decimal = Decimal("0")

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if self.timestamp.tzinfo is None:
            raise ValueError(
                "timestamp must be timezone-aware (use UTC)"
            )

    @property
    def spread(self) -> Decimal:
        """ask - bid."""
        return self.ask - self.bid

    @property
    def mid(self) -> Decimal:
        """(bid + ask) / 2."""
        return (self.bid + self.ask) / 2

    def as_dict(self) -> dict:
        """Serializable representation (Decimal → str for JSON)."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange.value,
            "timestamp": self.timestamp.isoformat(),
            "last": str(self.last),
            "bid": str(self.bid),
            "ask": str(self.ask),
            "bid_size": self.bid_size,
            "ask_size": self.ask_size,
            "volume": self.volume,
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "pre_close": str(self.pre_close),
        }


__all__ = ["MarketQuote"]
