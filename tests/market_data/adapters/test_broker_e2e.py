"""End-to-end broker → Quality Gate → Quote store → Paper gate (014 §16).

The scenario this suite pins down::

    Broker frame (vendor dialect)
        → BrokerMarketDataAdapter           (lifecycle, reconnect)
        → BrokerQuoteNormalizer → MarketQuote
        → QualityGate                       (FRESH / STALE)
        → QuoteService                      (the API / Dashboard read model)
        → PaperMarketFeed.check_order       (ALLOWED / BLOCKED)

    healthy frames          → FRESH   → Paper new order ALLOWED
    broker link drops       → adapter detects CONNECTION_LOST → RECONNECTING
                              → CONNECTED → auto-resubscribe → STREAMING
    a 30 s-delayed frame    → STALE   → Paper new order BLOCKED
    a fresh frame           → FRESH   → Paper new order ALLOWED

Everything runs on a :class:`VirtualClock` pinned to 2026-09-08 10:31 CST
(a Tuesday, mid continuous session) so the result never depends on when
the suite happens to run.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

try:  # pytest imports this module as ``adapters.test_broker_e2e``
    from .broker_helpers import (
        ScriptedProvider,
        VirtualClock,
        cst,
        make_config,
        raw_frame,
    )
except ImportError:  # pragma: no cover - direct execution fallback
    from broker_helpers import (  # type: ignore
        ScriptedProvider,
        VirtualClock,
        cst,
        make_config,
        raw_frame,
    )

from services.market_data.adapters.broker import (
    BrokerConnectionState,
    BrokerMarketDataAdapter,
    SubscriptionState,
)
from services.market_data.exceptions.broker_market_data_error import (
    BrokerConnectionLostError,
)
from services.market_data.paper.paper_feed_config import PaperFeedConfig
from services.market_data.paper.paper_feed_state import PaperFeedError
from services.market_data.paper.paper_market_feed import PaperMarketFeed
from services.market_data.quality.quality_config import QualityConfig
from services.market_data.quality.quality_gate import QualityGate
from services.market_data.quote_service import QuoteService
from services.market_data.validators.market_data_validator import (
    MarketDataValidator,
)

#: 2026-09-08 10:31:00 CST — Tuesday, continuous trading.
BASE = cst(2026, 9, 8, 10, 31, 0)


def at(seconds: float):
    return BASE + timedelta(seconds=seconds)


class RecordingAdapter(BrokerMarketDataAdapter):
    """Adapter that records its §7 state transitions."""

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.states: list[BrokerConnectionState] = []

    def _set_state(self, state: BrokerConnectionState) -> None:
        self.states.append(state)
        super()._set_state(state)


def _build_pipeline(clock: VirtualClock):
    """Wire broker → gate → quote store → paper gate on virtual time."""
    frames = [
        raw_frame("159852", timestamp=at(0)),
        raw_frame("159852", timestamp=at(1)),
        raw_frame("159852", timestamp=at(2)),
        # §10 — the broker link dies mid-flight
        BrokerConnectionLostError("simulated broker link dropped"),
        # a backlog frame whose 行情时间 is 30 s old by the time it lands
        raw_frame("159852", timestamp=at(20)),
        # the feed is healthy again
        raw_frame("159852", timestamp=at(55)),
    ]
    provider = ScriptedProvider(frames)
    adapter = RecordingAdapter(
        provider,
        config=make_config(),
        clock=lambda: clock.now + timedelta(milliseconds=45),
        sleep=lambda _seconds: None,
        max_quotes=5,
    )
    provider.on_exhausted = adapter.stop

    gate = QualityGate(
        config=QualityConfig(fresh_ms=3000, warning_ms=10000, stale_ms=10000)
    )
    # the stale window is deliberately huge: these are 2026-09-08 timestamps
    # judged by the *gate's* clock, not the validator's wall clock
    service = QuoteService(
        quality_gate=gate,
        validator=MarketDataValidator(stale_seconds=10**9),
    )
    paper = PaperMarketFeed(
        config=PaperFeedConfig(require_healthy_cache=False),
        quote_service=service,
        merge_engine=None,
        market_cache=None,
        clock=clock,
    )
    return adapter, provider, gate, service, paper


class TestBrokerEndToEnd:
    def test_full_broker_to_paper_lifecycle(self):
        clock = VirtualClock(BASE)
        adapter, provider, gate, service, paper = _build_pipeline(clock)

        # ── the adapter subscribes the Instrument Master universe (§6) ──
        adapter.connect()
        subscribed = adapter.subscribe_universe()
        assert len(subscribed) == 11
        assert adapter.connection_state() is BrokerConnectionState.SUBSCRIBED

        stream = adapter.stream()

        # ── phase 1: healthy broker frames → FRESH → orders allowed ──
        for now in (at(0), at(1), at(2)):
            clock.set(now)
            service.update(next(stream), now=now)

        assert service.quality("159852")["status"] == "FRESH"
        assert service.tradable("159852") is True
        assert service.stats()["quotes_accepted"] == 3

        clock.set(at(10))
        healthy = paper.check_order(
            "159852", quantity=100, at=at(10), order_timestamp=at(10)
        )
        assert healthy.allowed is True
        assert healthy.quality == "FRESH"
        assert healthy.fill_price == Decimal("1.050")
        assert healthy.fill_price_source == "ASK"

        # ── phase 2: the link dies; the adapter detects + recovers (§7) ──
        clock.set(at(50))
        stale_quote = next(stream)  # drop frame → reconnect → stale backlog
        service.update(stale_quote, now=at(50))

        assert BrokerConnectionState.CONNECTION_LOST in adapter.states
        assert BrokerConnectionState.RECONNECTING in adapter.states
        assert adapter.states.count(BrokerConnectionState.CONNECTED) == 2
        assert adapter.reconnect_count() == 1
        assert adapter.subscription_state() is SubscriptionState.SUBSCRIBED
        # §7 — a reconnect without a resubscribe is the dangerous case
        assert len(provider.subscribe_calls) == 2
        assert set(provider.subscribe_calls[0]) == set(subscribed)
        assert provider.subscribe_calls[1] == sorted(subscribed)
        assert adapter.is_connected() is True
        assert adapter.last_message_time() is not None

        # ── phase 3: 30 s of staleness → STALE → orders BLOCKED ──
        assert stale_quote.timestamp == at(20)
        assert service.quality("159852")["status"] == "STALE"
        assert service.tradable("159852") is False

        blocked = paper.check_order(
            "159852", quantity=100, at=at(51), order_timestamp=at(51)
        )
        assert blocked.allowed is False
        assert blocked.reason == PaperFeedError.MARKET_DATA_STALE.value
        assert blocked.quality == "STALE"
        assert blocked.quote_age_ms is not None
        assert blocked.quote_age_ms >= 30_000

        # ── phase 4: a fresh frame → FRESH → orders allowed again ──
        clock.set(at(55))
        fresh_quote = next(stream)
        service.update(fresh_quote, now=at(55))

        assert service.quality("159852")["status"] == "FRESH"
        assert service.tradable("159852") is True

        allowed = paper.check_order(
            "159852", quantity=100, at=at(56), order_timestamp=at(56)
        )
        assert allowed.allowed is True
        assert allowed.quality == "FRESH"
        assert allowed.fill_price is not None

        # §17 — every block left a trace, and the adapter is still healthy
        assert paper.stats()["blocked_by_reason"].get(
            PaperFeedError.MARKET_DATA_STALE.value
        ) == 1
        assert adapter.connection_state() is BrokerConnectionState.STREAMING
        assert adapter.stats()["quotes"] == 5
        assert adapter.stats()["malformed"] == 0

        # ── the read model the API / Dashboard consume (Commit 010/011) ──
        view = service.snapshot(["159852"])[0]
        assert view["symbol"] == "159852"
        assert view["quote"]["last"] == "1.050"
        assert gate.last_result("159852").status.value == "FRESH"

    def test_adapter_reports_health_for_monitoring(self):
        """Commit 013 Monitoring consumes exactly these accessors (§10)."""
        clock = VirtualClock(BASE)
        adapter, provider, _, _, _ = _build_pipeline(clock)

        adapter.connect()
        adapter.subscribe(["159852"])

        assert adapter.is_connected() is True
        assert adapter.connection_state() is BrokerConnectionState.SUBSCRIBED
        assert adapter.subscription_state() is SubscriptionState.SUBSCRIBED
        assert adapter.reconnect_count() == 0
        assert adapter.last_message_time() is None

        clock.set(at(0))
        quote = next(adapter.stream())
        assert quote.timestamp == at(0)
        assert adapter.last_message_time() is not None
        age = adapter.last_message_age_seconds()
        assert age is not None
        assert age == pytest.approx(0.0, abs=1e-3)

        health = adapter.health()
        assert health["connection"]["state"] == "STREAMING"
        assert health["subscription"]["symbols"] == ["159852"]
        assert health["market_data"]["quote_count"] == 1

        # secrets never appear in a health / config dump (§4)
        assert "token" not in adapter.as_dict()["config"]
