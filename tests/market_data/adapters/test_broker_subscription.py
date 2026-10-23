"""Subscription / Universe tests for the broker adapter (Commit 014 §6/§15).

The adapter must subscribe exactly the Instrument Master universe — it
is never allowed to keep a second symbol list.
"""
from __future__ import annotations

import dataclasses

import pytest

try:  # pytest imports this module as ``adapters.test_broker_subscription``
    from .broker_helpers import SEED_SYMBOLS, SimulatedBrokerProvider, make_adapter
except ImportError:  # pragma: no cover - direct execution fallback
    from broker_helpers import (  # type: ignore
        SEED_SYMBOLS,
        SimulatedBrokerProvider,
        make_adapter,
    )

from services.market_data.adapters.broker import (
    BrokerConnectionState,
    BrokerMarketDataAdapter,
    SubscriptionState,
)
from services.market_data.adapters.broker import (
    SimulatedBrokerProvider as _SimulatedProvider,
)
from services.market_data.exceptions.broker_market_data_error import (
    BrokerSubscriptionError,
)
from services.market_data.exceptions.market_data_error import (
    AdapterNotConnectedError,
)
from services.market_data.universe import Universe


def _adapter(universe=None) -> BrokerMarketDataAdapter:
    return make_adapter(
        SimulatedBrokerProvider(seed=3),
        universe=universe,
        max_quotes=1,
    )


class TestBrokerSubscription:
    def test_subscribe_before_connect_raises(self):
        adapter = _adapter()
        with pytest.raises(AdapterNotConnectedError):
            adapter.subscribe(["159852"])

    def test_unsubscribe_before_connect_raises(self):
        adapter = _adapter()
        with pytest.raises(AdapterNotConnectedError):
            adapter.unsubscribe(["159852"])

    def test_subscribe_universe_subscribes_all_eleven(self):
        adapter = _adapter()
        adapter.connect()
        subscribed = adapter.subscribe_universe()
        assert len(subscribed) == 11
        assert set(subscribed) == set(SEED_SYMBOLS)
        assert adapter.connection_state() is BrokerConnectionState.SUBSCRIBED
        assert adapter.subscription_state() is SubscriptionState.SUBSCRIBED

    def test_subscribe_single_symbol(self):
        adapter = _adapter()
        adapter.connect()
        adapter.subscribe(["159852"])
        assert adapter.subscribed_symbols() == ["159852"]
        assert adapter.subscription_state() is SubscriptionState.SUBSCRIBED

    def test_subscribe_normalises_vendor_symbol_shapes(self):
        """§3 — ``SZ159852`` / ``159852.SZ`` are the same instrument."""
        adapter = _adapter()
        adapter.connect()
        adapter.subscribe(["SZ159852", "159852.SZ", "sz-159852"])
        assert adapter.subscribed_symbols() == ["159852"]

    def test_unknown_symbol_is_rejected(self):
        adapter = _adapter()
        adapter.connect()
        with pytest.raises(BrokerSubscriptionError) as excinfo:
            adapter.subscribe(["999999"])
        assert "999999" in str(excinfo.value)
        assert adapter.subscribed_symbols() == []

    def test_unknown_symbol_does_not_subscribe_the_valid_ones(self):
        """A partially-bad request is rejected atomically."""
        adapter = _adapter()
        adapter.connect()
        with pytest.raises(BrokerSubscriptionError):
            adapter.subscribe(["159852", "999999"])
        assert adapter.subscribed_symbols() == []

    def test_disabled_instrument_is_not_subscribed(self):
        custom = Universe()
        instrument = custom.get("159852")
        assert instrument is not None
        custom._instruments["159852"] = dataclasses.replace(  # noqa: SLF001
            instrument, enabled=False
        )

        adapter = _adapter(universe=custom)
        adapter.connect()
        subscribed = adapter.subscribe_universe()
        assert "159852" not in subscribed
        assert adapter.skipped_symbols() == ["159852"]
        # the other ten are still requested
        assert len(subscribed) == 10

    def test_disabled_instrument_explicit_subscribe_is_skipped(self):
        custom = Universe()
        instrument = custom.get("513050")
        assert instrument is not None
        custom._instruments["513050"] = dataclasses.replace(  # noqa: SLF001
            instrument, enabled=False
        )
        adapter = _adapter(universe=custom)
        adapter.connect()
        adapter.subscribe(["513050", "159852"])
        assert adapter.subscribed_symbols() == ["159852"]
        assert adapter.skipped_symbols() == ["513050"]

    def test_unsubscribe(self):
        adapter = _adapter()
        adapter.connect()
        adapter.subscribe(["159852", "513050"])
        adapter.unsubscribe(["159852"])
        assert adapter.subscribed_symbols() == ["513050"]

    def test_unsubscribe_all_resets_subscription_state(self):
        adapter = _adapter()
        adapter.connect()
        adapter.subscribe(["159852", "513050"])
        adapter.unsubscribe(["159852", "513050"])
        assert adapter.subscribed_symbols() == []
        assert adapter.subscription_state() is SubscriptionState.UNSUBSCRIBED
        assert adapter.connection_state() is BrokerConnectionState.CONNECTED

    def test_unsubscribe_unknown_symbol_is_ignored(self):
        adapter = _adapter()
        adapter.connect()
        adapter.subscribe(["159852"])
        adapter.unsubscribe(["513050"])
        assert adapter.subscribed_symbols() == ["159852"]

    def test_provider_receives_the_subscription(self):
        provider = _SimulatedProvider(seed=3)
        adapter = make_adapter(provider, max_quotes=1)
        adapter.connect()
        adapter.subscribe_universe()
        assert len(provider.subscribe_calls) == 1
        assert set(provider.subscribe_calls[0]) == set(SEED_SYMBOLS)

    def test_subscribe_is_idempotent(self):
        provider = _SimulatedProvider(seed=3)
        adapter = make_adapter(provider, max_quotes=1)
        adapter.connect()
        adapter.subscribe(["159852"])
        adapter.subscribe(["159852"])
        assert adapter.subscribed_symbols() == ["159852"]
        assert provider.subscribe_calls == [["159852"], ["159852"]]
