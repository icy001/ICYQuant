"""Tests for MarketDataAdapter base class."""
from __future__ import annotations

from typing import Iterator

import pytest

from services.market_data.adapters.base import MarketDataAdapter
from services.market_data.domain.quote import MarketQuote
from services.market_data.exceptions.market_data_error import (
    AdapterAlreadyConnectedError,
    AdapterNotConnectedError,
)


class _DummyAdapter(MarketDataAdapter):
    """Minimal concrete adapter for testing the base class."""

    def __init__(self) -> None:
        self._connected = False

    @property
    def name(self) -> str:
        return "dummy"

    @property
    def connected(self) -> bool:
        return self._connected

    def connect(self) -> None:
        self._require_disconnected()
        self._connected = True

    def disconnect(self) -> None:
        self._connected = False

    def subscribe(self, symbols: list[str]) -> None:
        self._require_connected()

    def unsubscribe(self, symbols: list[str]) -> None:
        self._require_connected()

    def stream(self) -> Iterator[MarketQuote]:
        self._require_connected()
        return
        yield  # make it a generator


class TestAdapterGuards:
    def test_subscribe_before_connect_raises(self):
        adapter = _DummyAdapter()
        with pytest.raises(AdapterNotConnectedError):
            adapter.subscribe(["159852"])

    def test_stream_before_connect_raises(self):
        adapter = _DummyAdapter()
        with pytest.raises(AdapterNotConnectedError):
            list(adapter.stream())

    def test_unsubscribe_before_connect_raises(self):
        adapter = _DummyAdapter()
        with pytest.raises(AdapterNotConnectedError):
            adapter.unsubscribe(["159852"])

    def test_double_connect_raises(self):
        adapter = _DummyAdapter()
        adapter.connect()
        with pytest.raises(AdapterAlreadyConnectedError):
            adapter.connect()

    def test_connect_disconnect_reconnect(self):
        adapter = _DummyAdapter()
        assert not adapter.connected
        adapter.connect()
        assert adapter.connected
        adapter.disconnect()
        assert not adapter.connected
        adapter.connect()
        assert adapter.connected

    def test_disconnect_when_not_connected_is_noop(self):
        adapter = _DummyAdapter()
        adapter.disconnect()  # no error
        assert not adapter.connected


class TestAdapterCannotInstantiate:
    def test_abc_cannot_instantiate(self):
        with pytest.raises(TypeError):
            MarketDataAdapter()
