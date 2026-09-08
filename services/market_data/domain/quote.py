"""Unified market quote — the canonical A-share ETF/LOF quote.

Every market data adapter (mock, broker, third-party provider) must
convert its native tick into MarketQuote before pushing into ICYQuant.
This is the single contract point: downstream Strategy / Risk /
Paper Trading / Dashboard only ever see MarketQuote, never a raw
broker payload.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from typing import Optional

from .instrument import Exchange


class QuoteFreshness(str, Enum):
    """Freshness states for real-time quotes.

    FRESH   — quote age within fresh threshold (default ≤ 3s)
    WARNING — quote age between fresh and stale (default 3–10s)
    STALE   — quote older than stale threshold (default > 10s)
    OFFLINE — no quote received at all
    """

    FRESH = "FRESH"
    WARNING = "WARNING"
    STALE = "STALE"
    OFFLINE = "OFFLINE"


@dataclass(frozen=True)
class MarketQuote:
    """Level-1 quote for an A-share fund.

    All prices are in CNY, using Decimal for exact tick comparison
    (A-share ETF tick size = 0.001).  Sizes are in shares (lot size
    is enforced by the instrument, not by the quote).

    Fields:
        symbol             — 6-digit code, e.g. "159852"
        exchange           — SZSE / SSE
        timestamp          — exchange event time (tz-aware, source)
        received_timestamp — ICYQuant receive time (tz-aware)
        last               — last traded price
        bid                — best bid (limit buy)
        ask                — best ask (limit sell)
        bid_size           — total bid volume at best bid (shares)
        ask_size           — total ask volume at best ask (shares)
        volume             — cumulative volume since session open (shares)
        turnover           — cumulative turnover in CNY
        open               — session open price (optional, 0 if unknown)
        high               — session high (optional)
        low                — session low (optional)
        pre_close          — previous trading day close (optional)
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
    turnover: Decimal = Decimal("0")
    open: Decimal = Decimal("0")
    high: Decimal = Decimal("0")
    low: Decimal = Decimal("0")
    pre_close: Decimal = Decimal("0")
    received_timestamp: Optional[datetime] = None

    def __post_init__(self) -> None:
        if not self.symbol:
            raise ValueError("symbol must not be empty")
        if self.timestamp.tzinfo is None:
            raise ValueError(
                "timestamp must be timezone-aware (use UTC)"
            )
        if (
            self.received_timestamp is not None
            and self.received_timestamp.tzinfo is None
        ):
            raise ValueError(
                "received_timestamp must be timezone-aware (use UTC)"
            )

    @property
    def effective_received_at(self) -> datetime:
        """Receive time, falling back to timestamp when absent."""
        return self.received_timestamp or self.timestamp

    @property
    def latency_ms(self) -> int:
        """Ingest latency: received - exchange timestamp, in ms."""
        delta = self.effective_received_at - self.timestamp
        return max(0, int(delta.total_seconds() * 1000))

    @property
    def spread(self) -> Decimal:
        """ask - bid."""
        return self.ask - self.bid

    @property
    def mid(self) -> Decimal:
        """(bid + ask) / 2."""
        return (self.bid + self.ask) / 2

    @property
    def change(self) -> Decimal:
        """last - pre_close (0 when pre_close unknown)."""
        if self.pre_close <= 0:
            return Decimal("0")
        return self.last - self.pre_close

    @property
    def change_pct(self) -> Decimal:
        """(last - pre_close) / pre_close * 100, in percent."""
        if self.pre_close <= 0:
            return Decimal("0")
        return (self.change / self.pre_close * 100).quantize(
            Decimal("0.01")
        )

    def age_seconds(self, now: Optional[datetime] = None) -> float:
        """Quote age in seconds relative to `now` (default: UTC now)."""
        now = now or datetime.now(timezone.utc)
        return max(0.0, (now - self.timestamp).total_seconds())

    def freshness(
        self,
        *,
        fresh_seconds: float = 3.0,
        stale_seconds: float = 10.0,
        now: Optional[datetime] = None,
    ) -> QuoteFreshness:
        """Classify freshness against configurable thresholds."""
        age = self.age_seconds(now)
        if age <= fresh_seconds:
            return QuoteFreshness.FRESH
        if age <= stale_seconds:
            return QuoteFreshness.WARNING
        return QuoteFreshness.STALE

    def as_dict(self) -> dict:
        """Serializable representation (Decimal → str for JSON)."""
        return {
            "symbol": self.symbol,
            "exchange": self.exchange.value,
            "timestamp": self.timestamp.isoformat(),
            "received_timestamp": (
                self.effective_received_at.isoformat()
                if self.received_timestamp or self.timestamp
                else None
            ),
            "latency_ms": self.latency_ms,
            "last": str(self.last),
            "bid": str(self.bid),
            "ask": str(self.ask),
            "bid_size": self.bid_size,
            "ask_size": self.ask_size,
            "volume": self.volume,
            "turnover": str(self.turnover),
            "open": str(self.open),
            "high": str(self.high),
            "low": str(self.low),
            "pre_close": str(self.pre_close),
            "change": str(self.change),
            "change_pct": str(self.change_pct),
        }


__all__ = ["MarketQuote", "QuoteFreshness"]
