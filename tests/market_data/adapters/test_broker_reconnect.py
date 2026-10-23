"""Reconnect + resubscribe tests for the broker adapter (Commit 014 §7/§10).

The dangerous failure mode this suite guards against::

    Broker连接恢复
            ↓
    ICYQuant显示 CONNECTED
            ↓
    实际上没有行情
            ↓
    Paper/Strategy误以为行情正常

A reconnect that does not resubscribe is therefore treated as a bug.
"""
from __future__ import annotations

import pytest

try:  # pytest imports this module as ``adapters.test_broker_reconnect``
    from .broker_helpers import SimulatedBrokerProvider, make_adapter, make_config
except ImportError:  # pragma: no cover - direct execution fallback
    from broker_helpers import (  # type: ignore
        SimulatedBrokerProvider,
        make_adapter,
        make_config,
    )

from services.market_data.adapters.broker import (
    BrokerConnectionState,
    BrokerMarketDataAdapter,
    SubscriptionState,
)
from services.market_data.exceptions.broker_market_data_error import (
    BrokerReconnectError,
)


class RecordingAdapter(BrokerMarketDataAdapter):
    """Adapter that records every state transition (§7)."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.states: list[BrokerConnectionState] = []

    def _set_state(self, state: BrokerConnectionState) -> None:
        self.states.append(state)
        super()._set_state(state)


class TestBrokerReconnect:
    def test_drop_triggers_reconnect_and_resubscribe(self):
        provider = SimulatedBrokerProvider(seed=1, drop_after=2)
        adapter = make_adapter(provider, max_quotes=6)
        adapter.connect()
        adapter.subscribe(["159852"])

        quotes = list(adapter.stream())

        assert len(quotes) == 6
        assert adapter.reconnect_count() == 1
        assert adapter.connection_state() is BrokerConnectionState.STREAMING
        assert adapter.subscription_state() is SubscriptionState.SUBSCRIBED
        # §7 — the dangerous case: reconnected but not resubscribed
        assert provider.subscribe_calls == [["159852"], ["159852"]]
        assert provider.open_calls == 2

    def test_state_transition_sequence(self):
        provider = SimulatedBrokerProvider(seed=1, drop_after=1)
        adapter = RecordingAdapter(
            provider,
            config=make_config(),
            sleep=lambda _seconds: None,
            max_quotes=3,
        )
        adapter.connect()
        adapter.subscribe(["159852"])
        list(adapter.stream())

        assert adapter.states == [
            BrokerConnectionState.CONNECTING,
            BrokerConnectionState.CONNECTED,
            BrokerConnectionState.SUBSCRIBED,
            BrokerConnectionState.STREAMING,
            BrokerConnectionState.CONNECTION_LOST,
            BrokerConnectionState.RECONNECTING,
            BrokerConnectionState.CONNECTED,
            BrokerConnectionState.STREAMING,
        ]

    def test_auto_resubscribe_covers_every_subscribed_symbol(self):
        provider = SimulatedBrokerProvider(seed=1, drop_after=3)
        adapter = make_adapter(provider, max_quotes=5)
        adapter.connect()
        symbols = adapter.subscribe_universe()
        list(adapter.stream())

        assert len(provider.subscribe_calls) == 2
        assert set(provider.subscribe_calls[0]) == set(symbols)
        # the §7 resubscribe replays the *active* set, deterministically ordered
        assert provider.subscribe_calls[1] == sorted(symbols)

    def test_resubscribe_can_be_disabled_and_marks_desynced(self):
        provider = SimulatedBrokerProvider(seed=1, drop_after=1)
        config = make_config(resubscribe_on_reconnect=False)
        adapter = make_adapter(provider, config=config, max_quotes=3)
        adapter.connect()
        adapter.subscribe(["159852"])
        list(adapter.stream())

        assert adapter.reconnect_count() == 1
        # connection health is fine, subscription health is NOT
        assert adapter.connection_state() is BrokerConnectionState.STREAMING
        assert adapter.subscription_state() is SubscriptionState.DESYNCED
        assert provider.subscribe_calls == [["159852"]]

    def test_reconnect_uses_configured_delay(self):
        provider = SimulatedBrokerProvider(seed=1, drop_after=1)
        delays: list[float] = []
        adapter = BrokerMarketDataAdapter(
            provider,
            config=make_config(reconnect_seconds=1.5),
            sleep=delays.append,
            max_quotes=3,
        )
        adapter.connect()
        adapter.subscribe(["159852"])
        list(adapter.stream())

        assert delays == [1.5]

    def test_reconnect_exhaustion_raises_and_goes_offline(self):
        provider = SimulatedBrokerProvider(
            seed=1, drop_after=1, reopen_failures=99
        )
        config = make_config(max_reconnect_attempts=2)
        adapter = make_adapter(provider, config=config)
        adapter.connect()
        adapter.subscribe(["159852"])

        stream = adapter.stream()
        next(stream)  # one good frame
        last_seen = adapter.last_message_time()

        with pytest.raises(BrokerReconnectError) as excinfo:
            next(stream)

        assert "exhausted" in str(excinfo.value).lower()
        assert adapter.reconnect_count() == 0
        assert adapter.connection_state() is BrokerConnectionState.DISCONNECTED
        assert adapter.subscription_state() is SubscriptionState.UNSUBSCRIBED
        # §10 — monitoring still gets a usable last_message_time so it can
        # compute quote_age and raise MARKET_DATA_OFFLINE itself.
        assert adapter.last_message_time() == last_seen
        assert adapter.last_message_time() is not None
        assert adapter.is_connected() is False

    def test_market_data_health_survives_an_outage(self):
        """§7 — the three health dimensions answer different questions."""
        provider = SimulatedBrokerProvider(seed=1)
        adapter = make_adapter(provider, max_quotes=1)
        adapter.connect()
        adapter.subscribe(["159852"])
        next(adapter.stream())

        provider.simulate_disconnect()  # link dies, adapter not yet polled

        assert adapter.is_connected() is False
        health = adapter.health()
        assert health["connection"]["connected"] is True  # stale view
        assert health["connection"]["alive"] is False  # provider truth
        assert health["market_data"]["last_message_time"] is not None
