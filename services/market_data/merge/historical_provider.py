"""Historical bar provider — the history side of the merge (Commit 008).

Commit 008 does NOT redesign the historical data system.  History can
come from Parquet, PostgreSQL, a vendor or a broker API — the merge
engine only ever sees::

    provider.bars(symbol, timeframe, limit, before=..., anchor_price=...)

Phase 1 ships ``SyntheticHistoricalProvider``: a deterministic,
calendar-aware generator that stands in for a real store on the
always-on mock stack.  It is honest about what it is (``name =
"synthetic"``) and deliberately shares the mock adapter's seed prices
so a cold-start chart lines up with the live feed.

Calendar-awareness (§12): bars are generated only for trading-phase
minutes (09:30–11:29, 13:00–14:59 CST on trading days).  Lunch
breaks, nights and holidays are simply absent — they are not gaps
and never fabricated (§11).

Junction: the walk is anchored so the newest historical close equals
``anchor_price`` (the realtime series' first open, or the latest
quote) — the chart is seamless across the historical/realtime
boundary (§1).
"""
from __future__ import annotations

import logging
import random
import zlib
from datetime import date, datetime, time, timedelta, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Callable, Optional

from ..adapters.mock import _SEED_PRICES
from ..calendar.trading_calendar import CST, TradingCalendar, calendar
from ..domain.bar import Bar
from ..domain.instrument import Instrument

logger = logging.getLogger(__name__)

_TICK = Decimal("0.001")
_MIN_PRICE = Decimal("0.001")

# Bar-phase minutes on a trading day (CST wall clock, [start, end)).
_AM_START = time(9, 30)
_AM_END = time(11, 30)      # exclusive — 11:29 is the last AM bar minute
_PM_START = time(13, 0)
_PM_END = time(15, 0)      # exclusive — 14:59 is the last PM bar minute


def _to_cst(ts: datetime) -> datetime:
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(CST)


def _floor_minute(ts: datetime) -> datetime:
    return ts.replace(second=0, microsecond=0)


def _quantize(price: Decimal) -> Decimal:
    q = price.quantize(_TICK, rounding=ROUND_HALF_UP)
    return q if q >= _MIN_PRICE else _MIN_PRICE


def _minute_rng(symbol: str, minute: datetime) -> random.Random:
    """Deterministic per (symbol, minute) — stable across calls,
    processes and window shifts."""
    seed = zlib.crc32(f"{symbol}|{minute.isoformat()}".encode())
    return random.Random(seed)


class SyntheticHistoricalProvider:
    """Deterministic synthetic 1m history for Phase 1 (dev / mock).

    All bars are closed (``is_closed=True``): history only covers
    fully-elapsed minutes.  The current, in-progress minute belongs
    to the realtime side.
    """

    name = "synthetic"

    def __init__(
        self,
        *,
        trading_calendar: Optional[TradingCalendar] = None,
        clock: Optional[Callable[[], datetime]] = None,
    ) -> None:
        self._cal = trading_calendar or calendar
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    # ── protocol surface ───────────────────────────────────────

    def bars(
        self,
        symbol: str,
        timeframe: str = "1m",
        limit: int = 200,
        *,
        before: Optional[datetime] = None,
        anchor_price: Optional[Decimal] = None,
    ) -> list[Bar]:
        """Historical bars for ``symbol``, oldest first.

        before        — only bars with timestamp < before are
                        returned (the realtime junction minute is
                        excluded).  None → up to the last fully
                        closed bar minute at the clock's now.
        anchor_price  — the newest close is anchored here so the
                        series connects seamlessly to realtime.
        """
        if timeframe != "1m" or limit <= 0:
            return []
        limit = min(limit, 500)
        minutes = self._collect_minutes(before, limit)
        if not minutes:
            return []
        anchor = anchor_price if anchor_price is not None else (
            _SEED_PRICES.get(symbol, Decimal("1.000"))
        )
        closes = self._walk_closes(symbol, minutes, anchor)
        return self._build_bars(symbol, minutes, closes)

    # ── internals ─────────────────────────────────────────────

    def _collect_minutes(
        self, before: Optional[datetime], count: int
    ) -> list[datetime]:
        """Trading-phase minute stamps, walking backwards, ASC.

        Jumps skip nights, lunch breaks and non-trading days — the
        calendar decides what should exist (§12), so history is
        continuous *within* sessions only.
        """
        if before is not None:
            cursor = _floor_minute(_to_cst(before)) - timedelta(minutes=1)
        else:
            cursor = _floor_minute(_to_cst(self._clock())) - timedelta(
                minutes=1
            )
        out: list[datetime] = []
        guard = 0
        while len(out) < count and guard < 100_000:
            guard += 1
            day = cursor.date()
            if not self._cal.is_trading_day(day):
                cursor = self._day_end(day - timedelta(days=1))
                continue
            t = cursor.time()
            if t >= _PM_END:
                cursor = self._day_end(day)          # post-close → 14:59
                continue
            if t < _AM_START:
                cursor = self._day_end(day - timedelta(days=1))
                continue
            if _AM_END <= t < _PM_START:
                cursor = cursor.replace(
                    hour=11, minute=29, second=0, microsecond=0
                )                                     # lunch → 11:29
                continue
            out.append(cursor)
            cursor -= timedelta(minutes=1)
        out.reverse()
        return out

    @staticmethod
    def _day_end(day: date) -> datetime:
        """14:59 CST on the given calendar day (last bar minute)."""
        return datetime.combine(day, time(14, 59), CST)

    def _walk_closes(
        self, symbol: str, minutes: list[datetime], anchor: Decimal
    ) -> list[Decimal]:
        """Closes for each minute, walking *backwards* from the anchor.

        The per-minute drift factor depends only on (symbol, minute),
        so the walk is stable whatever window is requested — minute M
        always gets the same close for the same anchor.
        """
        closes: list[Decimal] = [Decimal(0)] * len(minutes)
        closes[-1] = _quantize(anchor)
        for i in range(len(minutes) - 1, 0, -1):
            factor = self._drift(symbol, minutes[i])
            # close[i-1] * factor ≈ close[i]  →  solve backwards
            closes[i - 1] = _quantize(closes[i] / factor)
        return closes

    @staticmethod
    def _drift(symbol: str, minute: datetime) -> Decimal:
        """Per-minute price drift factor (±0.2%), deterministic."""
        rng = _minute_rng(symbol, minute)
        return Decimal(str(1 + rng.uniform(-0.002, 0.002)))

    def _build_bars(
        self, symbol: str, minutes: list[datetime], closes: list[Decimal]
    ) -> list[Bar]:
        exchange = Instrument.infer_exchange(symbol)
        bars: list[Bar] = []
        for i, minute in enumerate(minutes):
            close = closes[i]
            rng = _minute_rng(symbol, minute)
            # open = previous close → continuous candles across the seam;
            # the drift key is the bar's OWN minute (matches the walk:
            # close[older] = quantize(close[newer] / drift(newer))), so
            # the value is stable whatever window boundary lands here
            if i == 0:
                open_px = _quantize(close / self._drift(symbol, minute))
            else:
                open_px = closes[i - 1]
            wick = Decimal(str(rng.randint(0, 3))) * _TICK
            high = _quantize(max(open_px, close) + wick)
            low = _quantize(max(
                _MIN_PRICE, min(open_px, close) - wick
            ))
            volume = rng.randint(50, 500) * 100
            turnover = (Decimal(volume) * close).quantize(
                Decimal("0.01"), rounding=ROUND_HALF_UP
            )
            bars.append(
                Bar(
                    symbol=symbol,
                    exchange=exchange,
                    timeframe="1m",
                    timestamp=minute.astimezone(timezone.utc),
                    open=open_px,
                    high=high,
                    low=low,
                    close=close,
                    volume=volume,
                    turnover=turnover,
                    is_closed=True,
                )
            )
        return bars


__all__ = ["SyntheticHistoricalProvider"]
