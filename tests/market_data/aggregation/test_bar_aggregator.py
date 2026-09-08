"""Tests for 1-minute BarAggregator (Commit 004).

Gate: Quote → OHLC, High/Low, Close, Volume delta, Timestamp
bucket, Bar close, Open bar update, Day boundary, Volume reset,
Gap detection.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from services.market_data.aggregation.bar_aggregator import BarAggregator
from services.market_data.domain.bar import Bar
from services.market_data.domain.instrument import Exchange
from services.market_data.domain.quote import MarketQuote


def _q(
    symbol: str = "159852",
    exchange: Exchange = Exchange.SZSE,
    ts: datetime | None = None,
    last: str = "1.000",
    volume: int = 0,
    turnover: str = "0",
) -> MarketQuote:
    return MarketQuote(
        symbol=symbol,
        exchange=exchange,
        timestamp=ts or datetime.now(timezone.utc),
        last=Decimal(last),
        bid=Decimal(last) - Decimal("0.001"),
        ask=Decimal(last),
        bid_size=10000,
        ask_size=10000,
        volume=volume,
        turnover=Decimal(turnover),
    )


def _minute(m: int, s: int = 0, base: datetime | None = None) -> datetime:
    """Helper: create a timestamp at minute m, second s."""
    base = base or datetime(2026, 9, 8, 9, 31, 0, tzinfo=timezone.utc)
    return base + timedelta(minutes=m, seconds=s)


class TestQuoteToOHLC:
    """Quote → OHLC basic."""

    def test_single_quote_opens_bar(self):
        agg = BarAggregator()
        q = _q(ts=_minute(0, 0), last="1.100", volume=100)
        result = agg.on_quote(q)
        assert result is None  # no bar closed yet
        bar = agg.current_bar("159852")
        assert bar is not None
        assert bar.open == Decimal("1.100")
        assert bar.close == Decimal("1.100")
        assert not bar.is_closed

    def test_multiple_quotes_accumulate(self):
        agg = BarAggregator()
        agg.on_quote(_q(ts=_minute(0, 0), last="1.100", volume=100))
        agg.on_quote(_q(ts=_minute(0, 10), last="1.120", volume=150))
        agg.on_quote(_q(ts=_minute(0, 30), last="1.090", volume=200))
        agg.on_quote(_q(ts=_minute(0, 50), last="1.115", volume=250))
        bar = agg.current_bar("159852")
        assert bar.open == Decimal("1.100")
        assert bar.high == Decimal("1.120")
        assert bar.low == Decimal("1.090")
        assert bar.close == Decimal("1.115")
        assert not bar.is_closed


class TestHighLowClose:
    def test_high_is_max(self):
        agg = BarAggregator()
        agg.on_quote(_q(ts=_minute(0, 0), last="1.000"))
        agg.on_quote(_q(ts=_minute(0, 10), last="1.050"))
        agg.on_quote(_q(ts=_minute(0, 20), last="1.020"))
        assert agg.current_bar("159852").high == Decimal("1.050")

    def test_low_is_min(self):
        agg = BarAggregator()
        agg.on_quote(_q(ts=_minute(0, 0), last="1.000"))
        agg.on_quote(_q(ts=_minute(0, 10), last="0.980"))
        agg.on_quote(_q(ts=_minute(0, 20), last="1.010"))
        assert agg.current_bar("159852").low == Decimal("0.980")

    def test_close_is_last(self):
        agg = BarAggregator()
        agg.on_quote(_q(ts=_minute(0, 0), last="1.000"))
        agg.on_quote(_q(ts=_minute(0, 10), last="1.050"))
        agg.on_quote(_q(ts=_minute(0, 20), last="1.020"))
        assert agg.current_bar("159852").close == Decimal("1.020")


class TestVolumeDelta:
    """Volume is delta (cumulative), not sum."""

    def test_volume_delta(self):
        agg = BarAggregator()
        agg.on_quote(_q(ts=_minute(0, 0), last="1.000", volume=1000))
        agg.on_quote(_q(ts=_minute(0, 10), last="1.010", volume=1500))
        agg.on_quote(_q(ts=_minute(0, 20), last="1.015", volume=2100))
        bar = agg.current_bar("159852")
        # 2100 - 1000 = 1100
        assert bar.volume == 1100

    def test_volume_reset_detected(self):
        """Volume going backwards → session reset, delta from 0."""
        agg = BarAggregator()
        agg.on_quote(_q(ts=_minute(0, 0), last="1.000", volume=5000))
        agg.on_quote(_q(ts=_minute(0, 10), last="1.010", volume=5200))
        # Reset: cumulative volume drops back (new session)
        agg.on_quote(_q(ts=_minute(0, 20), last="1.015", volume=300))
        bar = agg.current_bar("159852")
        # After reset, first_volume was set to 0, so delta = 300 - 0 = 300
        # Actually: last_vol was 5200, quote vol is 300 (< 5200) → reset triggered
        # first_volume → 0, last_volume → 300, delta = 300 - 0 = 300
        assert bar.volume == 300

    def test_turnover_delta(self):
        agg = BarAggregator()
        agg.on_quote(_q(ts=_minute(0, 0), last="1.000", volume=100, turnover="100.00"))
        agg.on_quote(_q(ts=_minute(0, 10), last="1.010", volume=200, turnover="202.00"))
        bar = agg.current_bar("159852")
        assert bar.turnover == Decimal("102.00")


class TestTimestampBucket:
    def test_same_minute_same_bar(self):
        agg = BarAggregator()
        agg.on_quote(_q(ts=_minute(0, 0), last="1.000"))
        agg.on_quote(_q(ts=_minute(0, 30), last="1.010"))
        agg.on_quote(_q(ts=_minute(0, 59), last="1.020"))
        bar = agg.current_bar("159852")
        assert bar.timestamp == _minute(0, 0)
        assert bar.close == Decimal("1.020")

    def test_next_minute_closes_bar(self):
        agg = BarAggregator()
        agg.on_quote(_q(ts=_minute(0, 0), last="1.000"))
        agg.on_quote(_q(ts=_minute(0, 30), last="1.010"))
        # Quote in next minute
        result = agg.on_quote(_q(ts=_minute(1, 5), last="1.015"))
        assert result is not None
        closed_bar, gaps = result
        assert closed_bar.is_closed
        assert closed_bar.close == Decimal("1.010")


class TestBarClose:
    def test_closed_bar_in_history(self):
        agg = BarAggregator()
        agg.on_quote(_q(ts=_minute(0, 0), last="1.000"))
        agg.on_quote(_q(ts=_minute(1, 0), last="1.010"))
        hist = agg.history("159852")
        assert len(hist) == 1
        assert hist[0].is_closed
        assert hist[0].open == Decimal("1.000")
        assert hist[0].close == Decimal("1.000")

    def test_current_bar_after_close(self):
        agg = BarAggregator()
        agg.on_quote(_q(ts=_minute(0, 0), last="1.000"))
        agg.on_quote(_q(ts=_minute(1, 0), last="1.010"))
        current = agg.current_bar("159852")
        assert current is not None
        assert not current.is_closed
        assert current.open == Decimal("1.010")


class TestOpenBarUpdate:
    def test_live_bar_updates_with_each_quote(self):
        agg = BarAggregator()
        agg.on_quote(_q(ts=_minute(0, 0), last="1.000"))
        bar1 = agg.current_bar("159852")
        assert bar1.close == Decimal("1.000")
        agg.on_quote(_q(ts=_minute(0, 10), last="1.050"))
        bar2 = agg.current_bar("159852")
        assert bar2.close == Decimal("1.050")
        assert bar2.high == Decimal("1.050")
        agg.on_quote(_q(ts=_minute(0, 20), last="0.980"))
        bar3 = agg.current_bar("159852")
        assert bar3.low == Decimal("0.980")
        assert bar3.close == Decimal("0.980")


class TestDayBoundary:
    """Volume reset at day boundary (cumulative volume drops)."""

    def test_day_boundary_volume_reset(self):
        agg = BarAggregator()
        # Day 1, minute 0: cumulative volume starts at 10000
        agg.on_quote(_q(ts=_minute(0, 0), last="1.000", volume=10000))
        agg.on_quote(_q(ts=_minute(0, 30), last="1.010", volume=12000))
        # Next minute: close bar 0, open bar 1
        agg.on_quote(_q(ts=_minute(1, 0), last="1.015", volume=13000))
        bar0 = agg.history("159852")[0]
        # Bar 0: first_vol=10000, last_vol=12000 (quote at :30), delta=2000
        # The quote at minute 1 opens a new bar, not added to bar 0
        assert bar0.volume == 2000  # 12000 - 10000

        # New day: cumulative volume resets to 500 (< 13000)
        next_day = datetime(2026, 9, 9, 9, 31, 0, tzinfo=timezone.utc)
        agg.on_quote(_q(ts=next_day, last="1.020", volume=500))
        bar1 = agg.history("159852")[1]
        # Bar 1 (09:32): first_vol=13000, last_vol=13000, delta=0
        assert bar1.volume == 0
        # New bar: fresh state, first_vol=500, last_vol=500, delta=0
        bar2 = agg.current_bar("159852")
        assert bar2.volume == 0

    def test_volume_reset_within_bar(self):
        """Volume drops mid-bar: reset triggers, delta from 0."""
        agg = BarAggregator()
        agg.on_quote(_q(ts=_minute(0, 0), last="1.000", volume=5000))
        agg.on_quote(_q(ts=_minute(0, 10), last="1.010", volume=5200))
        # Reset: cumulative volume drops
        agg.on_quote(_q(ts=_minute(0, 20), last="1.015", volume=300))
        bar = agg.current_bar("159852")
        # After reset: first_volume set to 0, last_volume=300 → delta=300
        assert bar.volume == 300


class TestGapDetection:
    """Gap: missing minutes between bars."""

    def test_gap_detected(self):
        agg = BarAggregator()
        agg.on_quote(_q(ts=_minute(0, 0), last="1.000"))
        # Skip minute 1, 2 — next quote at minute 3
        result = agg.on_quote(_q(ts=_minute(3, 0), last="1.010"))
        assert result is not None
        _closed, gaps = result
        assert len(gaps) == 2  # minute 1 and 2
        # bar_id format: {symbol}_{YYYYMMDDHHMM}, base=09:31 → 0932, 0933
        gap_str = " ".join(gaps)
        assert "0932" in gap_str
        assert "0933" in gap_str

    def test_no_gap_consecutive_minutes(self):
        agg = BarAggregator()
        agg.on_quote(_q(ts=_minute(0, 0), last="1.000"))
        result = agg.on_quote(_q(ts=_minute(1, 0), last="1.010"))
        assert result is not None
        _closed, gaps = result
        assert gaps == []

    def test_gap_list_queryable(self):
        agg = BarAggregator()
        agg.on_quote(_q(ts=_minute(0, 0), last="1.000"))
        agg.on_quote(_q(ts=_minute(5, 0), last="1.010"))
        gaps = agg.gaps("159852")
        assert len(gaps) == 4  # minutes 1, 2, 3, 4


class TestBarId:
    def test_bar_id_format(self):
        agg = BarAggregator()
        agg.on_quote(_q(ts=_minute(0, 0), last="1.000"))
        bar = agg.current_bar("159852")
        assert bar.bar_id.startswith("159852_")
        assert len(bar.bar_id) > len("159852_")

    def test_closed_bar_has_id(self):
        agg = BarAggregator()
        agg.on_quote(_q(ts=_minute(0, 0), last="1.000"))
        agg.on_quote(_q(ts=_minute(1, 0), last="1.010"))
        hist = agg.history("159852")
        assert all(b.bar_id for b in hist)


class TestMultipleSymbols:
    def test_independent_bars(self):
        agg = BarAggregator()
        agg.on_quote(_q(symbol="159852", ts=_minute(0, 0), last="1.000"))
        agg.on_quote(
            _q(symbol="513050", exchange=Exchange.SSE, ts=_minute(0, 0), last="1.600")
        )
        agg.on_quote(_q(symbol="159852", ts=_minute(0, 30), last="1.010"))
        agg.on_quote(
            _q(symbol="513050", exchange=Exchange.SSE, ts=_minute(0, 30), last="1.610")
        )
        b1 = agg.current_bar("159852")
        b2 = agg.current_bar("513050")
        assert b1.close == Decimal("1.010")
        assert b2.close == Decimal("1.610")


class TestCloseAll:
    def test_close_all(self):
        agg = BarAggregator()
        agg.on_quote(_q(ts=_minute(0, 0), last="1.000"))
        agg.on_quote(
            _q(symbol="513050", exchange=Exchange.SSE, ts=_minute(0, 0), last="1.600")
        )
        closed = agg.close_all()
        assert len(closed) == 2
        assert all(b.is_closed for b in closed)
        assert agg.current_bar("159852") is None
        assert agg.current_bar("513050") is None


class TestBarAsDict:
    def test_as_dict_fields(self):
        agg = BarAggregator()
        agg.on_quote(_q(ts=_minute(0, 0), last="1.000", volume=100, turnover="100.00"))
        bar = agg.current_bar("159852")
        d = bar.as_dict()
        for field in (
            "symbol", "exchange", "timeframe", "timestamp", "bar_id",
            "open", "high", "low", "close", "volume", "turnover",
            "is_closed", "change", "change_pct",
        ):
            assert field in d, f"missing {field}"
        assert d["timeframe"] == "1m"
        assert d["is_closed"] is False
