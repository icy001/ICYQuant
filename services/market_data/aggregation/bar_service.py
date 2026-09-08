"""Bar Service — bridges the quote pipeline to bar aggregation.

BarService hooks into QuoteService: every validated quote is pushed
into BarAggregator, producing 1m bars in real time.  The service
exposes:

- ``bars(symbol, limit)`` — latest N closed bars + 1 live bar
- ``current_bar(symbol)`` — the in-progress bar (is_closed=False)
- ``gaps(symbol)`` — missing bar IDs from detected gaps

Thread-safe: QuoteFeed writes from its thread while API reads.
"""
from __future__ import annotations

import logging
import threading
from typing import Optional

from ..domain.bar import Bar
from ..domain.quote import MarketQuote
from .bar_aggregator import BarAggregator

logger = logging.getLogger(__name__)


class BarService:
    """Thread-safe bar storage + aggregation hub."""

    def __init__(
        self,
        *,
        aggregator: Optional[BarAggregator] = None,
        max_bars_per_symbol: int = 500,
    ) -> None:
        self._lock = threading.Lock()
        self._aggregator = aggregator or BarAggregator()
        self._max_bars = max_bars_per_symbol

    def on_quote(self, quote: MarketQuote) -> Optional[tuple[Bar, list[str]]]:
        """Push a quote into aggregation.  Returns (closed_bar,
        missing_ids) when a bar is finalized, else None."""
        with self._lock:
            return self._aggregator.on_quote(quote)

    def bars(self, symbol: str, limit: int = 200) -> list[Bar]:
        """Latest closed bars + the current in-progress bar."""
        with self._lock:
            closed = self._aggregator.history(symbol, limit)
            current = self._aggregator.current_bar(symbol)
        bars = list(closed)
        if current is not None:
            bars.append(current)
        if limit > 0 and len(bars) > limit:
            bars = bars[-limit:]
        return bars

    def current_bar(self, symbol: str) -> Optional[Bar]:
        with self._lock:
            return self._aggregator.current_bar(symbol)

    def gaps(self, symbol: str) -> list[str]:
        with self._lock:
            return self._aggregator.gaps(symbol)

    def bar_count(self, symbol: str) -> int:
        with self._lock:
            return self._aggregator.bar_count(symbol)

    def close_all(self) -> list[Bar]:
        """Force-close all in-progress bars (e.g. on feed stop)."""
        with self._lock:
            return self._aggregator.close_all()

    def reset(self) -> None:
        with self._lock:
            self._aggregator.reset()

    def as_snapshot(self, symbol: str, limit: int = 200) -> dict:
        """Serializable view for API responses."""
        bars = self.bars(symbol, limit)
        return {
            "symbol": symbol,
            "timeframe": "1m",
            "bars": [b.as_dict() for b in bars],
            "count": len(bars),
            "closed_count": sum(1 for b in bars if b.is_closed),
            "has_live": any(not b.is_closed for b in bars),
            "gaps": self.gaps(symbol),
        }


# ── Singleton ─────────────────────────────────────────────────
bar_service = BarService()

__all__ = ["BarService", "bar_service"]
