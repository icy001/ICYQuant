"""Tests for BrokerMarketDataAdapter (Commit 014 §2 / §9 / §15)."""
from __future__ import annotations

from decimal import Decimal

import pytest

try:  # pytest imports this module as ``adapters.test_broker_adapter``
    from .broker_helpers import (
        SEED_SYMBOLS,
        VirtualClock,
        cst,
        make_adapter,
        make_config,
        raw_frame,
        run_script,
    )
except ImportError:  # pragma: no cover - direct execution fallback
    from broker_helpers import (  # type: ignore
        SEED_SYMBOLS,
        VirtualClock,
        cst,
        make_adapter,
        make_config,
        raw_frame,
        run_script,
    )

from services.market_data.adapters.broker import (
    BrokerConnectionState,
    BrokerMarketDataAdapter,
    SimulatedBrokerProvider,
    SubscriptionState,
    build_provider,
    provider_names,
    register_provider,
    unregister_provider,
)
from services.market_data.config.broker_config import BrokerMarketDataConfig
from services.market_data.domain.instrument import Exchange
from services.market_data.domain.quote import MarketQuote
from services.market_data.exceptions.broker_market_data_error import (
    BrokerConfigError,
    BrokerConnectionError,
    BrokerProviderUnknownError,
)
from services.market_data.exceptions.market_data_error import (
    AdapterAlreadyConnectedError,
    AdapterNotConnectedError,
)


class ExplodingProvider(SimulatedBrokerProvider):
    """Provider whose ``open`` blows up with a non-broker exception."""

    def open(self, config: BrokerMarketDataConfig) -> None:
        raise RuntimeError("vendor SDK exploded")


# ══════════════════════════════════════════════════════════════════
# lifecycle (§7)
# ══════════════════════════════════════════════════════════════════


class TestBrokerAdapterLifecycle:
    def test_initial_state(self):
        adapter = make_adapter()
        assert adapter.connected is False
        assert adapter.is_connected() is False
        assert adapter.connection_state() is BrokerConnectionState.DISCONNECTED
        assert adapter.subscription_state() is SubscriptionState.UNSUBSCRIBED
        assert adapter.reconnect_count() == 0
        assert adapter.last_message_time() is None
        assert adapter.subscribed_symbols() == []

    def test_connect_true_then_disconnect(self):
        adapter = make_adapter()
        adapter.connect()
        assert adapter.connected is True
        assert adapter.is_connected() is True
        assert adapter.connection_state() is BrokerConnectionState.CONNECTED

        adapter.disconnect()
        assert adapter.connected is False
        assert adapter.is_connected() is False
        assert adapter.connection_state() is BrokerConnectionState.DISCONNECTED

    def test_double_connect_raises(self):
        adapter = make_adapter()
        adapter.connect()
        with pytest.raises(AdapterAlreadyConnectedError):
            adapter.connect()

    def test_disconnect_when_disconnected_is_noop(self):
        adapter = make_adapter()
        adapter.disconnect()
        assert adapter.connection_state() is BrokerConnectionState.DISCONNECTED

    def test_connect_to_disabled_config_raises(self):
        adapter = make_adapter(config=make_config(enabled=False))
        with pytest.raises(BrokerConfigError):
            adapter.connect()
        assert adapter.connection_state() is BrokerConnectionState.DISCONNECTED

    def test_connect_wraps_vendor_exception(self):
        adapter = make_adapter(
            ExplodingProvider(), config=make_config(), max_quotes=None
        )
        with pytest.raises(BrokerConnectionError) as excinfo:
            adapter.connect()
        assert "vendor SDK exploded" in str(excinfo.value)
        assert adapter.connection_state() is BrokerConnectionState.DISCONNECTED

    def test_stream_before_connect_raises(self):
        adapter = make_adapter()
        with pytest.raises(AdapterNotConnectedError):
            list(adapter.stream())

    def test_stream_with_empty_subscription_yields_nothing(self):
        adapter = make_adapter()
        adapter.connect()
        assert list(adapter.stream()) == []


# ══════════════════════════════════════════════════════════════════
# provider registry (§5)
# ══════════════════════════════════════════════════════════════════


class TestProviderRegistry:
    def test_simulated_is_registered(self):
        assert "simulated" in provider_names()

    def test_build_provider_returns_simulated(self):
        provider = build_provider(make_config(provider="simulated"))
        assert isinstance(provider, SimulatedBrokerProvider)

    def test_build_provider_unknown_raises(self):
        with pytest.raises(BrokerProviderUnknownError):
            build_provider(make_config(provider="does-not-exist"))

    def test_adapter_requires_registered_provider(self):
        with pytest.raises(BrokerProviderUnknownError):
            BrokerMarketDataAdapter(
                config=BrokerMarketDataConfig(provider="does-not-exist")
            )

    def test_register_and_unregister(self):
        register_provider("unit-test-provider", lambda cfg: SimulatedBrokerProvider())
        try:
            assert "unit-test-provider" in provider_names()
            assert isinstance(
                build_provider(make_config(provider="unit-test-provider")),
                SimulatedBrokerProvider,
            )
        finally:
            unregister_provider("unit-test-provider")
        assert "unit-test-provider" not in provider_names()

    def test_duplicate_registration_raises(self):
        with pytest.raises(BrokerConfigError):
            register_provider("simulated", lambda cfg: SimulatedBrokerProvider())


# ══════════════════════════════════════════════════════════════════
# streaming + field mapping (§3 / §15)
# ══════════════════════════════════════════════════════════════════


class TestBrokerAdapterStream:
    def test_stream_yields_market_quotes(self):
        provider = SimulatedBrokerProvider(seed=7)
        adapter = make_adapter(provider, max_quotes=5)
        adapter.connect()
        adapter.subscribe(["159852"])

        quotes = list(adapter.stream())
        assert len(quotes) == 5
        for quote in quotes:
            assert isinstance(quote, MarketQuote)
            assert quote.symbol == "159852"
            assert quote.exchange is Exchange.SZSE
            assert isinstance(quote.last, Decimal)
            assert quote.last > 0

    def test_stream_bid_never_above_ask(self):
        adapter = make_adapter(
            SimulatedBrokerProvider(seed=11), max_quotes=25
        )
        adapter.connect()
        adapter.subscribe(SEED_SYMBOLS)
        for quote in adapter.stream():
            assert quote.bid <= quote.ask

    def test_stream_exchange_matches_symbol_prefix(self):
        adapter = make_adapter(
            SimulatedBrokerProvider(seed=13), max_quotes=40
        )
        adapter.connect()
        adapter.subscribe(SEED_SYMBOLS)
        for quote in adapter.stream():
            if quote.symbol.startswith(("15", "16")):
                assert quote.exchange is Exchange.SZSE
            elif quote.symbol.startswith(("50", "51")):
                assert quote.exchange is Exchange.SSE

    def test_stream_preserves_exchange_timestamp(self):
        exchange_ts = cst(2026, 9, 8, 10, 31, 0, 123000)
        provider = SimulatedBrokerProvider(
            seed=1, clock=lambda: exchange_ts
        )
        adapter = make_adapter(provider, max_quotes=3)
        adapter.connect()
        adapter.subscribe(["159852"])
        for quote in adapter.stream():
            assert quote.timestamp == exchange_ts

    def test_stream_stamps_latency_from_receive_clock(self):
        """§8 — latency = received_timestamp − exchange_timestamp."""
        clock = VirtualClock(cst(2026, 9, 8, 10, 31, 0))
        # provider emits 行情时间 = 10:31:00, adapter "receives" 45 ms later
        provider = SimulatedBrokerProvider(seed=1, clock=clock)
        adapter = make_adapter(
            provider, clock=clock, latency_ms=45, max_quotes=1
        )
        adapter.connect()
        adapter.subscribe(["159852"])
        quote = next(adapter.stream())
        assert quote.latency_ms == 45

    def test_stream_updates_last_message_time_and_stats(self):
        adapter = make_adapter(
            SimulatedBrokerProvider(seed=5), max_quotes=4
        )
        adapter.connect()
        adapter.subscribe(["159852"])
        assert adapter.last_message_time() is None

        quotes = list(adapter.stream())
        assert len(quotes) == 4
        assert adapter.last_message_time() is not None
        assert adapter.last_message_age_seconds() is not None
        assert adapter.stats()["quotes"] == 4

    def test_max_quotes_limit(self):
        adapter = make_adapter(
            SimulatedBrokerProvider(seed=5), max_quotes=3
        )
        adapter.connect()
        adapter.subscribe(["159852"])
        assert len(list(adapter.stream())) == 3

    def test_stop_interrupts_stream(self):
        adapter = make_adapter(SimulatedBrokerProvider(seed=5))
        adapter.connect()
        adapter.subscribe(["159852"])
        stream = adapter.stream()
        next(stream)
        adapter.stop()
        assert list(stream) == []

    def test_volume_and_turnover_are_non_decreasing(self):
        adapter = make_adapter(
            SimulatedBrokerProvider(seed=17), max_quotes=30
        )
        adapter.connect()
        adapter.subscribe(["159852"])
        previous = {}
        for quote in adapter.stream():
            last = previous.get(quote.symbol)
            if last is not None:
                assert quote.volume >= last.volume
                assert quote.turnover >= last.turnover
            previous[quote.symbol] = quote

    def test_full_cycle(self):
        adapter = make_adapter(
            SimulatedBrokerProvider(seed=99), max_quotes=5
        )
        adapter.connect()
        adapter.subscribe(["159852", "513050"])
        assert len(adapter.subscribed_symbols()) == 2
        assert len(list(adapter.stream())) == 5
        adapter.unsubscribe(["159852"])
        assert adapter.subscribed_symbols() == ["513050"]
        adapter.disconnect()
        assert adapter.connected is False
        assert adapter.subscription_state() is SubscriptionState.UNSUBSCRIBED


# ══════════════════════════════════════════════════════════════════
# malformed frames (§9)
# ══════════════════════════════════════════════════════════════════


class TestBrokerAdapterMalformedFrames:
    def test_non_mapping_frame_is_dropped(self):
        frames = ["not-a-mapping", raw_frame()]
        adapter, _, quotes = _run_scripted(frames, max_quotes=1)
        assert len(quotes) == 1
        assert adapter.stats()["malformed"] == 1

    def test_missing_symbol_frame_is_dropped(self):
        bad = raw_frame()
        del bad["证券代码"]
        adapter, _, quotes = _run_scripted([bad, raw_frame()], max_quotes=1)
        assert len(quotes) == 1
        assert adapter.stats()["malformed"] == 1

    def test_missing_price_frame_is_dropped(self):
        bad = raw_frame()
        del bad["最新价"]
        adapter, _, quotes = _run_scripted([bad, raw_frame()], max_quotes=1)
        assert len(quotes) == 1
        assert adapter.stats()["malformed"] == 1

    def test_bad_timestamp_frame_is_dropped(self):
        bad = raw_frame(timestamp="not-a-time")
        adapter, _, quotes = _run_scripted([bad, raw_frame()], max_quotes=1)
        assert len(quotes) == 1
        assert adapter.stats()["malformed"] == 1

    def test_all_malformed_frames_yield_nothing(self):
        adapter, provider, quotes = _run_scripted(
            ["nope", {"证券代码": "159852"}]
        )
        assert quotes == []
        assert adapter.stats()["malformed"] == 2
        assert provider.subscribe_calls == [["159852"]]


def _run_scripted(frames, *, max_quotes=None, symbols=("159852",)):
    return run_script(frames, max_quotes=max_quotes, symbols=symbols)


# ══════════════════════════════════════════════════════════════════
# data safety — no silent sanitising (§9 / §15)
# ══════════════════════════════════════════════════════════════════


class TestBrokerAdapterDataSafety:
    def test_negative_last_is_passed_through(self):
        """§9 — ``last = -1`` must NOT be clamped to 0 / None.

        The adapter maps it faithfully so the Quality Gate can raise
        ``INVALID_PRICE`` and quarantine it, with an audit trail.
        """
        frames = [raw_frame(last="-1"), raw_frame(last="1.050")]
        _, _, quotes = _run_scripted(frames, max_quotes=2)
        assert quotes[0].last == Decimal("-1")
        assert quotes[1].last == Decimal("1.050")

    def test_stale_quote_is_passed_through(self):
        """A stale exchange timestamp is the Quality Gate's call, not
        the adapter's."""
        stale = raw_frame(timestamp=cst(2026, 9, 8, 9, 0))
        _, _, quotes = _run_scripted([stale], max_quotes=1)
        assert quotes[0].timestamp == cst(2026, 9, 8, 9, 0)

    def test_timestamp_regression_is_passed_through(self):
        """§15 — an out-of-order tick reaches the gate (which rejects
        it) instead of being silently reordered or dropped."""
        newer = raw_frame(timestamp=cst(2026, 9, 8, 10, 31, 5))
        older = raw_frame(timestamp=cst(2026, 9, 8, 10, 31, 0))
        _, _, quotes = _run_scripted([newer, older], max_quotes=2)
        assert [q.timestamp for q in quotes] == [
            cst(2026, 9, 8, 10, 31, 5),
            cst(2026, 9, 8, 10, 31, 0),
        ]


# ══════════════════════════════════════════════════════════════════
# health snapshot for Commit 013 Monitoring (§7 / §10)
# ══════════════════════════════════════════════════════════════════


class TestBrokerAdapterHealth:
    def test_health_separates_the_three_dimensions(self):
        adapter = make_adapter(
            SimulatedBrokerProvider(seed=3), max_quotes=2
        )
        adapter.connect()
        adapter.subscribe(["159852"])
        list(adapter.stream())

        health = adapter.health()
        assert health["provider"] == "simulated"
        assert health["connection"]["state"] == "STREAMING"
        assert health["connection"]["connected"] is True
        assert health["subscription"]["state"] == "SUBSCRIBED"
        assert health["subscription"]["symbols"] == ["159852"]
        assert health["market_data"]["quote_count"] == 2
        assert health["market_data"]["last_message_time"] is not None

    def test_is_connected_reflects_provider_liveness(self):
        provider = SimulatedBrokerProvider(seed=3)
        adapter = make_adapter(provider, max_quotes=1)
        adapter.connect()
        adapter.subscribe(["159852"])
        next(adapter.stream())

        assert adapter.is_connected() is True
        provider.simulate_disconnect()  # §10 — link drops
        assert adapter.is_connected() is False

    def test_as_dict_redacts_credentials(self):
        config = make_config(
            provider="simulated", token="super-secret", account="acct-1"
        )
        adapter = make_adapter(config=config)
        payload = adapter.as_dict()
        assert payload["config"]["has_credentials"] is True
        assert payload["config"]["account"] == "acct-1"
        assert "token" not in payload["config"]
        assert "super-secret" not in str(payload)

    def test_repr_is_informative(self):
        adapter = make_adapter()
        adapter.connect()
        assert "BrokerMarketDataAdapter" in repr(adapter)
        assert "simulated" in repr(adapter)
