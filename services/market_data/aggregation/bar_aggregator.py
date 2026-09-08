"""1-minute Bar Aggregator (Commit 004).

Converts a stream of MarketQuote objects into 1-minute OHLCV bars.
The aggregator handles:

- **Minute bucketing**: quotes within [09:31:00, 09:31:59] all
  belong to the 09:31 bar.  Bar timestamp = floor(ts, 1m).

- **OHLC**: open = first quote's last; high = max(last); low =
  min(last); close = last quote's last.

- **Volume delta**: A-share feeds report cumulative session volume.
  The bar's volume = last_cumulative - first_cumulative, not a sum.
  Handles volume reset (session boundary / reconnect).

- **Turnover delta**: same delta logic as volume.

- **Bar close**: when a quote arrives in the next minute, the
  current bar is finalized (is_closed = True) and a new bar opens.

- **Gap detection**: if a quote arrives ≥2 minutes after the
  current bar, the intervening minutes are recorded as missing bars
  (no synthetic OHLC fabricated).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Optional

from ..domain.bar import Bar
from ..domain.instrument import Exchange
from ..domain.quote import MarketQuote

logger = logging.getLogger(__name__)

_TIMEFRAME = "1m"


def _floor_minute(ts: datetime) -> datetime:
    """Floor a datetime to the start of its minute."""
    return ts.replace(second=0, microsecond=0)


@dataclass
class _BarState:
    """Mutable accumulator for one in-progress bar."""

    symbol: str
    exchange: Exchange
    bar_ts: datetime
    open: Decimal = Decimal("0")
    high: Decimal = Decimal("0")
    low: Decimal = Decimal("0")
    close: Decimal = Decimal("0")
    first_volume: int = -1   # cumulative volume at first quote
    last_volume: int = 0     # cumulative volume at latest quote
    first_turnover: Decimal = Decimal("-1")
    last_turnover: Decimal = Decimal("0")
    quote_count: int = 0
    is_closed: bool = False

    def to_bar(self) -> Bar:
        # volume delta = last - first (or 0 if first unknown)
        if self.first_volume >= 0:
            vol = max(0, self.last_volume - self.first_volume)
        else:
            vol = 0
        if self.first_turnover >= 0:
            turnover = max(Decimal("0"), self.last_turnover - self.first_turnover)
        else:
            turnover = Decimal("0")
        return Bar(
            symbol=self.symbol,
            exchange=self.exchange,
            timeframe=_TIMEFRAME,
            timestamp=self.bar_ts,
            open=self.open,
            high=self.high,
            low=self.low,
            close=self.close,
            volume=vol,
            turnover=turnover,
            is_closed=self.is_closed,
        )

    def update(self, quote: MarketQuote) -> None:
        """Accumulate a new quote into this bar."""
        if self.quote_count == 0:
            self.open = quote.last
            self.high = quote.last
            self.low = quote.last
            self.first_volume = quote.volume
            self.first_turnover = quote.turnover
        else:
            if quote.last > self.high:
                self.high = quote.last
            if quote.last < self.low:
                self.low = quote.last
        self.close = quote.last
        # Volume: detect reset (cumulative went backwards)
        if quote.volume < self.last_volume:
            # session boundary or reconnect — treat quote.volume
            # as the new baseline (delta = quote.volume - 0)
            self.first_volume = 0
            self.first_turnover = Decimal("0")
        self.last_volume = quote.volume
        self.last_turnover = quote.turnover
        self.quote_count += 1


class BarAggregator:
    """Stateful 1-minute bar aggregator for a set of symbols.

    Usage::

        agg = BarAggregator()
        for quote in quote_stream:
            result = agg.on_quote(quote)
            if result:
                closed_bar, missing_bars = result
                ...

    ``on_quote`` returns ``None`` while the current bar is still
    accumulating, or a ``(closed_bar, [missing_bar_ids])`` tuple
    when a bar is finalized (either by the next minute or by
    explicit :meth:`close_current`).
    """

    def __init__(self) -> None:
        # symbol → current in-progress bar state
        self._states: dict[str, _BarState] = {}
        # symbol → list of closed bars (history)
        self._history: dict[str, list[Bar]] = {}
        # symbol → set of missing bar_ids (gaps)
        self._gaps: dict[str, list[str]] = {}
        self._max_history = 500  # per symbol

    def on_quote(
        self, quote: MarketQuote
    ) -> Optional[tuple[Bar, list[str]]]:
        """Feed a quote; return (closed_bar, missing_ids) if a bar
        was finalized by this quote, otherwise None."""
        symbol = quote.symbol
        q_minute = _floor_minute(quote.timestamp)

        state = self._states.get(symbol)

        # No current bar → open a new one
        if state is None:
            new_state = _BarState(
                symbol=symbol,
                exchange=quote.exchange,
                bar_ts=q_minute,
            )
            new_state.update(quote)
            self._states[symbol] = new_state
            return None

        # Same minute → accumulate
        if q_minute == state.bar_ts:
            state.update(quote)
            return None

        # New minute → close current bar, detect gaps, open new bar
        closed_bar = self._close_bar(symbol, state, q_minute)

        # Gap detection: if q_minute > state.bar_ts + 1 min, the
        # intervening minutes have no data.
        missing_ids: list[str] = []
        expected = state.bar_ts + timedelta(minutes=1)
        while expected < q_minute:
            gap_id = f"{symbol}_{expected.strftime('%Y%m%d%H%M')}"
            missing_ids.append(gap_id)
            expected += timedelta(minutes=1)
        if missing_ids:
            self._gaps.setdefault(symbol, []).extend(missing_ids)
            logger.info(
                "gap detected for %s: %d missing bars",
                symbol, len(missing_ids),
            )

        # Open new bar
        new_state = _BarState(
            symbol=symbol,
            exchange=quote.exchange,
            bar_ts=q_minute,
        )
        new_state.update(quote)
        self._states[symbol] = new_state

        return closed_bar, missing_ids

    def _close_bar(
        self, symbol: str, state: _BarState, next_bar_ts: datetime
    ) -> Bar:
        """Finalize the current bar and push to history."""
        state.is_closed = True
        bar = state.to_bar()
        self._history.setdefault(symbol, []).append(bar)
        # Trim history
        hist = self._history[symbol]
        if len(hist) > self._max_history:
            self._history[symbol] = hist[-self._max_history :]
        return bar

    def close_current(self, symbol: str) -> Optional[Bar]:
        """Force-close the current in-progress bar (e.g. on feed
        stop).  Returns the closed bar or None if no bar exists."""
        state = self._states.get(symbol)
        if state is None:
            return None
        bar = self._close_bar(symbol, state, datetime.now(timezone.utc))
        del self._states[symbol]
        return bar

    def close_all(self) -> list[Bar]:
        """Force-close all in-progress bars."""
        closed: list[Bar] = []
        for symbol in list(self._states.keys()):
            bar = self.close_current(symbol)
            if bar:
                closed.append(bar)
        return closed

    # ── read path ───────────────────────────────────────────────

    def current_bar(self, symbol: str) -> Optional[Bar]:
        """The in-progress (is_closed=False) bar, if any."""
        state = self._states.get(symbol)
        if state is None:
            return None
        return state.to_bar()

    def history(
        self, symbol: str, limit: int = 200
    ) -> list[Bar]:
        """Closed bars for a symbol, most recent last, up to limit."""
        hist = self._history.get(symbol, [])
        if limit <= 0:
            return list(hist)
        return list(hist[-limit:])

    def gaps(self, symbol: str) -> list[str]:
        """List of missing bar IDs (gaps) for a symbol."""
        return list(self._gaps.get(symbol, []))

    def bar_count(self, symbol: str) -> int:
        """Total closed bars for a symbol."""
        return len(self._history.get(symbol, []))

    def reset(self) -> None:
        """Clear all state (for test isolation)."""
        self._states.clear()
        self._history.clear()
        self._gaps.clear()


__all__ = ["BarAggregator"]
