"""Replay event — the unit of replayed market history (Commit 012 §8).

Downstream code is never handed a DataFrame row or a raw provider
object.  It receives one :class:`ReplayEvent` per replayed instant, so
Strategy / Paper Trading consume replay exactly the way they consume
live data::

    Historical Data
          ↓
    ReplayEngine          ← builds the event stream
          ↓
    ReplayEvent (BAR)
          ↓
    Quality Gate (006)
          ↓
    Paper Market Feed (009)
          ↓
    Strategy / Paper Trading

Event types (first version, §8)::

    BAR     a 1m OHLCV bar          ← the only one replay emits today
    QUOTE   a level-1 quote         ← reserved, never synthesised

§12 — the boundary that matters most
------------------------------------

If history only contains 1m OHLCV, replay emits **BAR** events and never
invents 60 ticks to look like a quote feed.  Fabricated quotes would
look like a real replay while actually being artificial data, which is
strictly worse than saying "we only have bars".  ``QUOTE`` therefore
exists in the enum so a future quote-level source can be replayed
**without changing the event contract**, and nothing in this commit
produces one.

§13 — one timestamp, two meanings
---------------------------------

``ReplayEvent.timestamp`` is the **virtual** (knowable) time: the bar's
*close*.  ``data.timestamp`` stays the bar's *open* — the exchange's own
stamp, never rewritten.  Consumers gate on the former and read the
latter, which is what keeps replay free of lookahead (§26).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Optional

from ..domain.bar import Bar
from ..domain.instrument import Exchange
from ..domain.quote import MarketQuote


class ReplayEventType(str, Enum):
    """Event kinds the engine can emit (§8)."""

    QUOTE = "QUOTE"
    BAR = "BAR"


@dataclass(frozen=True)
class ReplayEvent:
    """One replayed instant.

    ``sequence`` is the event's global position in the run, so two runs
    of the same window produce identical ``(sequence, symbol,
    timestamp)`` triples — determinism is therefore checkable, not
    merely claimed (§25).
    """

    timestamp: datetime                  # §13 virtual time = knowable-at
    event_type: ReplayEventType
    symbol: str
    data: object                         # Bar (BAR) / MarketQuote (QUOTE)
    sequence: int = 0
    phase: str = ""
    tradable: bool = False
    gap_before: bool = False
    crosses_session: bool = False
    quality: dict = field(default_factory=dict)

    # ── convenience accessors ────────────────────────────────────

    @property
    def virtual_time(self) -> datetime:
        """Alias of ``timestamp`` — the clock replay runs on (§5)."""
        return self.timestamp

    @property
    def bar(self) -> Optional[Bar]:
        """The bar payload, or ``None`` for non-bar events."""
        return self.data if isinstance(self.data, Bar) else None

    @property
    def quote(self) -> Optional[MarketQuote]:
        """The quote payload, or ``None`` for non-quote events."""
        return self.data if isinstance(self.data, MarketQuote) else None

    @property
    def exchange(self) -> Optional[Exchange]:
        return getattr(self.data, "exchange", None)

    @property
    def timeframe(self) -> str:
        return str(getattr(self.data, "timeframe", "") or "")

    @property
    def bar_id(self) -> str:
        return str(getattr(self.data, "bar_id", "") or "")

    @property
    def last(self) -> Optional[Decimal]:
        """Last traded price carried by the event."""
        bar = self.bar
        if bar is not None:
            return bar.close
        quote = self.quote
        return quote.last if quote is not None else None

    def as_quote(self) -> MarketQuote:
        """Derive a **trade-only** quote from a BAR event (§12).

        ``bid`` / ``ask`` are deliberately zero: replay reconstructs
        *trades*, not a Level-1 book, so Paper must price at LAST.  The
        session-level ``open`` / ``high`` / ``low`` / ``pre_close`` are
        left zero too — a single replayed minute cannot know them.
        ``close`` of the bar becomes ``last`` and the virtual close time
        becomes both ``timestamp`` and ``received_timestamp``, so the
        §7 lookahead guard sees a quote that arrived exactly when it
        became knowable.
        """
        if self.event_type is ReplayEventType.QUOTE:
            quote = self.quote
            if quote is not None:
                return quote
        bar = self.bar
        if bar is None:
            raise ValueError(
                f"event {self.sequence} has no quote/bar payload to price"
            )
        return MarketQuote(
            symbol=bar.symbol,
            exchange=bar.exchange,
            timestamp=self.timestamp,
            last=bar.close,
            bid=Decimal("0"),
            ask=Decimal("0"),
            volume=bar.volume,
            turnover=bar.turnover,
            received_timestamp=self.timestamp,
        )

    def as_dict(self) -> dict:
        payload = (
            self.data.as_dict()
            if hasattr(self.data, "as_dict")
            else self.data
        )
        return {
            "sequence": self.sequence,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type.value,
            "symbol": self.symbol,
            "phase": self.phase,
            "tradable": self.tradable,
            "gap_before": self.gap_before,
            "crosses_session": self.crosses_session,
            "quality": dict(self.quality),
            "data": payload,
        }


__all__ = ["ReplayEventType", "ReplayEvent"]
