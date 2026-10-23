"""Tests for MockMarketDataAdapter."""
from __future__ import annotations

import itertools

import pytest

from services.market_data.adapters.mock import MockMarketDataAdapter
from services.market_data.domain.instrument import Exchange
from services.market_data.domain.quote import MarketQuote
from services.market_data.exceptions.market_data_error import (
    AdapterAlreadyConnectedError,
    AdapterNotConnectedError,
)

SEED_SYMBOLS = [
    "159852", "513050", "159890", "159559", "159569",
    "515880", "159871", "513310", "501225", "161116", "165520",
]


class TestMockAdapterLifecycle:
    def test_connect(self):
        adapter = MockMarketDataAdapter()
        assert not adapter.connected
        adapter.connect()
        assert adapter.connected

    def test_disconnect(self):
        adapter = MockMarketDataAdapter()
        adapter.connect()
        adapter.disconnect()
        assert not adapter.connected

    def test_double_connect_raises(self):
        adapter = MockMarketDataAdapter()
        adapter.connect()
        with pytest.raises(AdapterAlreadyConnectedError):
            adapter.connect()

    def test_disconnect_when_not_connected_noop(self):
        adapter = MockMarketDataAdapter()
        adapter.disconnect()
        assert not adapter.connected


class TestMockAdapterSubscribe:
    def test_subscribe_before_connect_raises(self):
        adapter = MockMarketDataAdapter()
        with pytest.raises(AdapterNotConnectedError):
            adapter.subscribe(["159852"])

    def test_subscribe_single(self):
        adapter = MockMarketDataAdapter()
        adapter.connect()
        adapter.subscribe(["159852"])
        assert "159852" in adapter.subscribed_symbols

    def test_subscribe_multiple(self):
        adapter = MockMarketDataAdapter()
        adapter.connect()
        adapter.subscribe(SEED_SYMBOLS)
        assert len(adapter.subscribed_symbols) == 11

    def test_subscribe_unknown_symbol_auto_registers(self):
        adapter = MockMarketDataAdapter()
        adapter.connect()
        adapter.subscribe(["999999"])
        assert "999999" in adapter.subscribed_symbols

    def test_unsubscribe(self):
        adapter = MockMarketDataAdapter()
        adapter.connect()
        adapter.subscribe(["159852", "513050"])
        adapter.unsubscribe(["159852"])
        assert "159852" not in adapter.subscribed_symbols
        assert "513050" in adapter.subscribed_symbols

    def test_unsubscribe_not_subscribed_is_noop(self):
        adapter = MockMarketDataAdapter()
        adapter.connect()
        adapter.unsubscribe(["159852"])  # no error


class TestMockAdapterStream:
    def test_stream_before_connect_raises(self):
        adapter = MockMarketDataAdapter()
        with pytest.raises(AdapterNotConnectedError):
            list(adapter.stream())

    def test_stream_empty_subscription_yields_nothing(self):
        adapter = MockMarketDataAdapter()
        adapter.connect()
        # empty subscription → generator returns immediately
        quotes = list(adapter.stream())
        assert quotes == []

    def test_stream_yields_market_quotes(self):
        adapter = MockMarketDataAdapter(seed=42, max_quotes=5)
        adapter.connect()
        adapter.subscribe(["159852"])
        quotes = list(adapter.stream())
        assert len(quotes) == 5
        for q in quotes:
            assert isinstance(q, MarketQuote)
            assert q.symbol == "159852"
            assert q.exchange == Exchange.SZSE

    def test_stream_all_11_symbols(self):
        adapter = MockMarketDataAdapter(seed=42, max_quotes=50)
        adapter.connect()
        adapter.subscribe(SEED_SYMBOLS)
        quotes = list(adapter.stream())
        assert len(quotes) == 50
        produced_symbols = {q.symbol for q in quotes}
        # With 50 quotes over 11 symbols, at least 5 should appear
        assert len(produced_symbols) >= 5
        # All produced symbols must be in the seed set
        assert produced_symbols.issubset(set(SEED_SYMBOLS))

    def test_stream_prices_are_positive(self):
        adapter = MockMarketDataAdapter(seed=42, max_quotes=10)
        adapter.connect()
        adapter.subscribe(["159852"])
        for q in adapter.stream():
            assert q.last > 0
            assert q.bid > 0
            assert q.ask > 0

    def test_stream_bid_less_equal_ask(self):
        adapter = MockMarketDataAdapter(seed=42, max_quotes=20)
        adapter.connect()
        adapter.subscribe(SEED_SYMBOLS)
        for q in adapter.stream():
            assert q.bid <= q.ask

    def test_stream_volume_accumulates(self):
        adapter = MockMarketDataAdapter(seed=42, max_quotes=10)
        adapter.connect()
        adapter.subscribe(["159852"])
        quotes = list(adapter.stream())
        # Volume should be non-decreasing
        for i in range(1, len(quotes)):
            if quotes[i].symbol == quotes[i - 1].symbol:
                assert quotes[i].volume >= quotes[i - 1].volume

    def test_stream_exchange_matches_symbol(self):
        adapter = MockMarketDataAdapter(seed=42, max_quotes=30)
        adapter.connect()
        adapter.subscribe(SEED_SYMBOLS)
        for q in adapter.stream():
            if q.symbol.startswith(("15", "16")):
                assert q.exchange == Exchange.SZSE
            elif q.symbol.startswith(("50", "51")):
                assert q.exchange == Exchange.SSE

    def test_stream_max_quotes_limit(self):
        adapter = MockMarketDataAdapter(seed=42, max_quotes=3)
        adapter.connect()
        adapter.subscribe(["159852"])
        quotes = list(adapter.stream())
        assert len(quotes) == 3


class TestMockAdapterFullCycle:
    """Full lifecycle: connect → subscribe → stream → unsubscribe → disconnect."""

    def test_full_cycle(self):
        adapter = MockMarketDataAdapter(seed=99, max_quotes=5)
        adapter.connect()
        adapter.subscribe(["159852", "513050"])
        quotes = list(itertools.islice(adapter.stream(), 5))
        assert len(quotes) == 5
        adapter.unsubscribe(["159852"])
        adapter.disconnect()
        assert not adapter.connected
