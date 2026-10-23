"""Tests for QuoteService + QuoteFeed — real-time quote pipeline hub.

Commit 003 gate: quote storage, freshness classification
(FRESH/WARNING/STALE/OFFLINE), feed lifecycle (subscribe /
unsubscribe via adapter), latency stamping.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from services.market_data.adapters.mock import MockMarketDataAdapter
from services.market_data.domain.instrument import Exchange
from services.market_data.domain.quote import MarketQuote, QuoteFreshness
from services.market_data.exceptions.market_data_error import (
    MarketDataError,
    StaleQuoteError,
    TimestampRegressionError,
)
from services.market_data.quote_service import (
    FreshnessThresholds,
    QuoteFeed,
    QuoteService,
)
from services.market_data.validators.market_data_validator import (
    MarketDataValidator,
)


def _quote(**overrides) -> MarketQuote:
    defaults = dict(
        symbol="159852",
        exchange=Exchange.SZSE,
        timestamp=datetime.now(timezone.utc),
        last=Decimal("1.234"),
        bid=Decimal("1.233"),
        ask=Decimal("1.234"),
        bid_size=120000,
        ask_size=95000,
        volume=1000000,
        turnover=Decimal("1234000.00"),
    )
    defaults.update(overrides)
    return MarketQuote(**defaults)


def _service(**kw) -> QuoteService:
    # validator with generous staleness so tests control timestamps
    kw.setdefault("validator", MarketDataValidator(stale_seconds=600))
    return QuoteService(**kw)


class TestQuoteServiceUpdate:
    def test_update_stores_quote(self):
        svc = _service()
        svc.update(_quote())
        assert svc.latest("159852") is not None
        assert svc.latest("159852").last == Decimal("1.234")

    def test_update_stamps_received_timestamp(self):
        svc = _service()
        q = svc.update(_quote())
        assert q.received_timestamp is not None
        assert q.received_timestamp.tzinfo is not None

    def test_update_replaces_latest(self):
        svc = _service()
        svc.update(_quote(last=Decimal("1.100")))
        svc.update(_quote(last=Decimal("1.200")))
        assert svc.latest("159852").last == Decimal("1.200")

    def test_update_rejects_invalid_quote(self):
        svc = _service()
        with pytest.raises(MarketDataError):
            svc.update(_quote(bid=Decimal("1.500"), ask=Decimal("1.400")))
        assert svc.latest("159852") is None

    def test_update_rejects_stale_quote(self):
        svc = QuoteService(
            validator=MarketDataValidator(stale_seconds=5)
        )
        old = datetime.now(timezone.utc) - timedelta(seconds=60)
        with pytest.raises(StaleQuoteError):
            svc.update(_quote(timestamp=old))
        assert svc.latest("159852") is None

    def test_update_rejects_timestamp_regression(self):
        svc = _service()
        t1 = datetime.now(timezone.utc)
        t0 = t1 - timedelta(seconds=10)
        svc.update(_quote(timestamp=t1))
        with pytest.raises(TimestampRegressionError):
            svc.update(_quote(timestamp=t0))
        # stored quote unchanged
        assert svc.latest("159852").timestamp == t1


class TestQuoteServiceFreshness:
    def test_fresh_quote_is_live(self):
        svc = _service()
        svc.update(_quote(timestamp=datetime.now(timezone.utc)))
        view = svc.snapshot(["159852"])[0]
        assert view["status"] == "LIVE"

    def test_warning_band(self):
        svc = _service()
        # 5s old: between fresh (3s) and stale (10s)
        svc.update(
            _quote(timestamp=datetime.now(timezone.utc) - timedelta(seconds=5))
        )
        view = svc.snapshot(["159852"])[0]
        assert view["status"] == "WARNING"

    def test_stale_quote(self):
        svc = _service()
        svc.update(
            _quote(timestamp=datetime.now(timezone.utc) - timedelta(seconds=30))
        )
        view = svc.snapshot(["159852"])[0]
        assert view["status"] == "STALE"

    def test_offline_when_no_quote(self):
        svc = _service()
        view = svc.snapshot(["513050"])[0]
        assert view["status"] == "OFFLINE"
        assert view["quote"] is None

    def test_custom_thresholds(self):
        svc = QuoteService(
            validator=MarketDataValidator(stale_seconds=600),
            thresholds=FreshnessThresholds(fresh_seconds=1, stale_seconds=2),
        )
        svc.update(
            _quote(timestamp=datetime.now(timezone.utc) - timedelta(seconds=1.5))
        )
        view = svc.snapshot(["159852"])[0]
        assert view["status"] == "WARNING"

    def test_age_seconds_in_view(self):
        svc = _service()
        svc.update(
            _quote(timestamp=datetime.now(timezone.utc) - timedelta(seconds=2))
        )
        view = svc.snapshot(["159852"])[0]
        assert 1.5 <= view["age_seconds"] <= 3.0

    def test_latency_ms_in_view(self):
        svc = _service()
        q = _quote()
        svc.update(q)
        view = svc.snapshot(["159852"])[0]
        # received - exchange timestamp ≈ 0ms (same machine)
        assert view["quote"]["latency_ms"] < 1000


class TestQuoteServiceStats:
    def test_stats_counts(self):
        svc = _service()
        svc.update(_quote())
        svc.update(_quote(symbol="513050", exchange=Exchange.SSE))
        stats = svc.stats()
        assert stats["symbols_tracked"] == 2
        assert stats["quotes_accepted"] == 2
        assert stats["quotes_rejected"] == 0
        assert stats["thresholds"]["fresh_seconds"] == 3.0
        assert stats["thresholds"]["stale_seconds"] == 10.0

    def test_mark_rejected(self):
        svc = _service()
        svc.mark_rejected()
        assert svc.stats()["quotes_rejected"] == 1


class TestQuoteFeed:
    def test_feed_start_and_stop(self):
        svc = _service()
        adapter = MockMarketDataAdapter(seed=42)
        feed = QuoteFeed(adapter, svc, interval=0.01)
        assert not feed.running
        feed.start(symbols=["159852", "513050"])
        assert feed.running
        # let some quotes flow
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if svc.latest("159852") is not None and svc.latest("513050") is not None:
                break
            time.sleep(0.01)
        feed.stop()
        assert not feed.running
        assert not adapter.connected

    def test_feed_populates_quotes(self):
        svc = _service()
        adapter = MockMarketDataAdapter(seed=7)
        feed = QuoteFeed(adapter, svc, interval=0.01)
        feed.start(symbols=["159852"])
        deadline = time.time() + 2.0
        while time.time() < deadline:
            if svc.latest("159852") is not None:
                break
            time.sleep(0.01)
        feed.stop()
        q = svc.latest("159852")
        assert q is not None
        assert q.symbol == "159852"
        assert q.received_timestamp is not None

    def test_feed_all_11_symbols(self):
        svc = _service()
        adapter = MockMarketDataAdapter(seed=99)
        feed = QuoteFeed(adapter, svc, interval=0.005)
        symbols = [
            "159852", "513050", "159890", "159559", "159569",
            "515880", "159871", "513310", "501225", "161116", "165520",
        ]
        feed.start(symbols=symbols)
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if all(svc.latest(s) is not None for s in symbols):
                break
            time.sleep(0.01)
        feed.stop()
        for s in symbols:
            assert svc.latest(s) is not None, f"{s} never received a quote"

    def test_feed_idempotent_start(self):
        svc = _service()
        adapter = MockMarketDataAdapter(seed=1)
        feed = QuoteFeed(adapter, svc, interval=0.05)
        feed.start(symbols=["159852"])
        feed.start(symbols=["159852"])  # no error, no double thread
        assert feed.running
        feed.stop()


class TestMarketQuoteFreshnessUnit:
    """Direct MarketQuote.freshness() unit tests."""

    def test_fresh(self):
        q = _quote(timestamp=datetime.now(timezone.utc))
        assert q.freshness() == QuoteFreshness.FRESH

    def test_warning(self):
        q = _quote(
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=5)
        )
        assert q.freshness() == QuoteFreshness.WARNING

    def test_stale(self):
        q = _quote(
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=15)
        )
        assert q.freshness() == QuoteFreshness.STALE

    def test_change_pct(self):
        q = _quote(
            last=Decimal("1.234"), pre_close=Decimal("1.200")
        )
        assert q.change == Decimal("0.034")
        assert q.change_pct == Decimal("2.83")

    def test_latency_ms(self):
        ts = datetime.now(timezone.utc) - timedelta(milliseconds=53)
        q = _quote(timestamp=ts, received_timestamp=datetime.now(timezone.utc))
        assert 40 <= q.latency_ms <= 200

    def test_turnover_in_dict(self):
        q = _quote(turnover=Decimal("2930000.00"))
        assert q.as_dict()["turnover"] == "2930000.00"
