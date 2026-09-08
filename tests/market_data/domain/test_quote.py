"""Tests for MarketQuote domain model."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from services.market_data.domain.instrument import Exchange
from services.market_data.domain.quote import MarketQuote


def _make_quote(**overrides) -> MarketQuote:
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
    )
    defaults.update(overrides)
    return MarketQuote(**defaults)


class TestMarketQuoteCreation:
    def test_basic_creation(self):
        q = _make_quote()
        assert q.symbol == "159852"
        assert q.exchange == Exchange.SZSE
        assert q.last == Decimal("1.234")
        assert q.bid == Decimal("1.233")
        assert q.ask == Decimal("1.234")
        assert q.bid_size == 120000
        assert q.ask_size == 95000
        assert q.volume == 1000000

    def test_defaults(self):
        q = MarketQuote(
            symbol="159852",
            exchange=Exchange.SZSE,
            timestamp=datetime.now(timezone.utc),
            last=Decimal("1.0"),
            bid=Decimal("0.999"),
            ask=Decimal("1.0"),
        )
        assert q.bid_size == 0
        assert q.ask_size == 0
        assert q.volume == 0
        assert q.open == Decimal("0")
        assert q.high == Decimal("0")
        assert q.low == Decimal("0")
        assert q.pre_close == Decimal("0")

    def test_empty_symbol_raises(self):
        with pytest.raises(ValueError, match="symbol must not be empty"):
            _make_quote(symbol="")


class TestMarketQuoteProperties:
    def test_spread(self):
        q = _make_quote(
            bid=Decimal("1.230"),
            ask=Decimal("1.235"),
        )
        assert q.spread == Decimal("0.005")

    def test_mid(self):
        q = _make_quote(
            bid=Decimal("1.230"),
            ask=Decimal("1.234"),
        )
        assert q.mid == Decimal("1.232")


class TestMarketQuoteTimestamp:
    def test_naive_timestamp_raises(self):
        with pytest.raises(ValueError, match="timezone-aware"):
            _make_quote(timestamp=datetime.now())

    def test_utc_timestamp_ok(self):
        q = _make_quote(timestamp=datetime.now(timezone.utc))
        assert q.timestamp.tzinfo is not None


class TestMarketQuoteAsDict:
    def test_as_dict(self):
        ts = datetime.now(timezone.utc)
        q = _make_quote(timestamp=ts)
        d = q.as_dict()
        assert d["symbol"] == "159852"
        assert d["exchange"] == "SZSE"
        assert d["last"] == "1.234"
        assert d["bid"] == "1.233"
        assert d["ask"] == "1.234"
        assert d["bid_size"] == 120000
        assert d["ask_size"] == 95000
        assert d["timestamp"] == ts.isoformat()


class TestAllSeedSymbols:
    SEED = [
        "159852", "513050", "159890", "159559", "159569",
        "515880", "159871", "513310", "501225", "161116", "165520",
    ]

    @pytest.mark.parametrize("symbol", SEED)
    def test_can_create_quote_for_each(self, symbol):
        from services.market_data.domain.instrument import Instrument

        ex = Instrument.infer_exchange(symbol)
        q = MarketQuote(
            symbol=symbol,
            exchange=ex,
            timestamp=datetime.now(timezone.utc),
            last=Decimal("1.0"),
            bid=Decimal("0.999"),
            ask=Decimal("1.0"),
        )
        assert q.symbol == symbol


class TestCommit003Extensions:
    """turnover / received_timestamp / freshness (Commit 003)."""

    def test_turnover_default_zero(self):
        q = _make_quote()
        assert q.turnover == Decimal("0")

    def test_turnover_roundtrip(self):
        q = _make_quote(turnover=Decimal("2930000.00"))
        assert q.as_dict()["turnover"] == "2930000.00"

    def test_received_timestamp_default_none(self):
        q = _make_quote()
        assert q.received_timestamp is None
        # effective falls back to exchange timestamp
        assert q.effective_received_at == q.timestamp

    def test_received_timestamp_stamped(self):
        ts = datetime.now(timezone.utc)
        recv = ts + timedelta(milliseconds=53)
        q = _make_quote(timestamp=ts, received_timestamp=recv)
        assert q.latency_ms == 53

    def test_received_timestamp_naive_raises(self):
        with pytest.raises(ValueError, match="received_timestamp"):
            _make_quote(received_timestamp=datetime.now())

    def test_age_seconds(self):
        q = _make_quote(
            timestamp=datetime.now(timezone.utc) - timedelta(seconds=2)
        )
        assert 1.0 <= q.age_seconds() <= 3.0

    def test_change_and_change_pct(self):
        q = _make_quote(
            last=Decimal("1.234"), pre_close=Decimal("1.200")
        )
        assert q.change == Decimal("0.034")
        assert q.change_pct == Decimal("2.83")

    def test_change_zero_without_pre_close(self):
        q = _make_quote(pre_close=Decimal("0"))
        assert q.change == Decimal("0")
        assert q.change_pct == Decimal("0")
