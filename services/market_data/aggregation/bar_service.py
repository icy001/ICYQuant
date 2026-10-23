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
    """Thread-safe bar storage + aggregation hub.

    ``enforce_session`` (Commit 005): when True, quotes outside bar
    phases (pre-open, auction, lunch break, post-close, non-trading
    days) are NOT aggregated — no lunch bars, no overnight bars, no
    phantom bars on holidays.  Market closures are also excluded
    from gap detection (they are not data gaps).

    Default False so the always-on Mock feed (Phase 1) keeps the
    Dashboard live outside market hours; real adapters enable it.
    """

    def __init__(
        self,
        *,
        aggregator: Optional[BarAggregator] = None,
        max_bars_per_symbol: int = 500,
        enforce_session: bool = False,
    ) -> None:
        self._lock = threading.Lock()
        self._enforce_session = enforce_session
        if enforce_session:
            from ..calendar.trading_calendar import calendar

            aggregator = aggregator or BarAggregator(
                gap_filter=calendar.is_bar_phase
            )
        self._aggregator = aggregator or BarAggregator()
        self._max_bars = max_bars_per_symbol

    def on_quote(self, quote: MarketQuote) -> Optional[tuple[Bar, list[str]]]:
        """Push a quote into aggregation.  Returns (closed_bar,
        missing_ids) when a bar is finalized, else None."""
        if self._enforce_session:
            from ..calendar.trading_calendar import calendar

            if not calendar.is_bar_phase(quote.timestamp):
                return None  # market closure — no bar
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
        # Bar quality (Commit 006): structural OHLCV check per bar —
        # marked, never modified.
        from ..quality.bar_quality import validate_bar

        invalid_bars: list[str] = []
        for b in bars:
            if not validate_bar(b).valid:
                invalid_bars.append(b.bar_id)
        return {
            "symbol": symbol,
            "timeframe": "1m",
            "bars": [b.as_dict() for b in bars],
            "count": len(bars),
            "closed_count": sum(1 for b in bars if b.is_closed),
            "has_live": any(not b.is_closed for b in bars),
            "gaps": self.gaps(symbol),
            "quality": {
                "checked": len(bars),
                "invalid_count": len(invalid_bars),
                "invalid_bars": invalid_bars,
            },
        }


# ── Singleton ─────────────────────────────────────────────────
bar_service = BarService()

__all__ = ["BarService", "bar_service"]
