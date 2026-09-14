"""Tests for the Paper Trading Market Feed (Commit 009).

Gate (§19):

* Market Feed  — 11-symbol subscription, quote retrieval, 1m bar
  retrieval, stream
* Quality      — FRESH allows; WARNING / STALE / INVALID /
  QUARANTINED block
* Session      — CONTINUOUS_AM / CONTINUOUS_PM allow; LUNCH_BREAK /
  CLOSE / POST_CLOSE / non-trading day block
* Fill         — BUY → ASK, SELL → BID, no book → LAST, slippage
* Risk / Integ. — invalid lot size, lookahead, old quote, future
  quote, Redis degraded
* Frontend     — PAPER badge, NO REAL MONEY, market / quote /
  quality / order status
* §13          — the existing PaperTradingSession engine is reused
  unchanged behind the adapter
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from apps.runtime.paper import PaperMarketFeedAdapter, RealMarketPaperSession
from apps.runtime.paper_trading import PaperAccount, SignalSpec
from services.market_data.aggregation.bar_service import BarService
from services.market_data.calendar.trading_calendar import calendar
from services.market_data.domain.bar import Bar
from services.market_data.domain.instrument import (
    Exchange,
    Instrument,
    InstrumentType,
)
from services.market_data.domain.quote import MarketQuote
from services.market_data.merge.bar_merge import BarMergeEngine
from services.market_data.merge.historical_provider import (
    SyntheticHistoricalProvider,
)
from services.market_data.paper import (
    DISCLAIMER,
    FillPriceSource,
    PaperBlockedError,
    PaperFeedConfig,
    PaperFeedError,
    PaperFeedState,
    PaperMarketFeed,
)
from services.market_data.universe import universe

# ── deterministic timestamps (CST wall-clock in UTC form) ──────────
# 2026-09-08 is a Tuesday and a trading day (see calendar tests).
TUE_AM = datetime(2026, 9, 8, 2, 45, tzinfo=timezone.utc)     # 10:45 CONTINUOUS_AM
TUE_LUNCH = datetime(2026, 9, 8, 3, 45, tzinfo=timezone.utc)  # 11:45 LUNCH_BREAK
TUE_PM = datetime(2026, 9, 8, 6, 0, tzinfo=timezone.utc)      # 14:00 CONTINUOUS_PM
TUE_CLOSE = datetime(2026, 9, 8, 7, 2, tzinfo=timezone.utc)   # 15:02 CLOSE
TUE_POST = datetime(2026, 9, 8, 7, 30, tzinfo=timezone.utc)   # 15:30 POST_CLOSE
SUN_NOON = datetime(2026, 9, 6, 4, 0, tzinfo=timezone.utc)    # Sunday NON_TRADING


# ── fakes ──────────────────────────────────────────────────────────
class FakeClock:
    """Mutable clock — deterministic session / age arithmetic."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


class FakeQuoteService:
    """QuoteService double: same read surface the real one exposes."""

    def __init__(
        self,
        quotes: dict[str, MarketQuote] | None = None,
        quality: dict[str, dict] | None = None,
    ) -> None:
        self._quotes = dict(quotes or {})
        self._quality = dict(quality or {})

    def put(self, quote: MarketQuote) -> None:
        self._quotes[quote.symbol] = quote

    def put_quality(self, symbol: str, view: dict | None) -> None:
        if view is None:
            self._quality.pop(symbol, None)
        else:
            self._quality[symbol] = view

    def latest(self, symbol: str):
        return self._quotes.get(symbol)

    def quality(self, symbol: str):
        return self._quality.get(symbol)


class FakeBarService:
    def __init__(self, bars: dict[str, list[Bar]] | None = None) -> None:
        self._bars = dict(bars or {})

    def bars(self, symbol: str, limit: int = 200) -> list[Bar]:
        return list(self._bars.get(symbol, []))[-limit:]

    def current_bar(self, symbol: str):
        bars = self._bars.get(symbol) or []
        return bars[-1] if bars else None


class FakeCache:
    """MarketCache double (§12 degraded-cache policy)."""

    def __init__(self, *, degraded: bool = False) -> None:
        self._degraded = degraded

    @property
    def degraded(self) -> bool:
        return self._degraded

    def trading_allowed(self) -> bool:
        return not self._degraded

    def health(self) -> dict:
        return {
            "backend": "fake",
            "state": "DEGRADED" if self._degraded else "HEALTHY",
        }


class FakeInstruments:
    """Instrument Master double with a non-default lot size (§8)."""

    def __init__(self, lot_size: int) -> None:
        self._lot = lot_size

    def get(self, symbol: str):
        return Instrument(
            symbol=symbol,
            exchange=Exchange.SZSE,
            instrument_type=InstrumentType.ETF,
            name=f"Fake {symbol}",
            lot_size=self._lot,
        )


def _quote(**overrides) -> MarketQuote:
    defaults = dict(
        symbol="159852",
        exchange=Exchange.SZSE,
        timestamp=TUE_AM,
        last=Decimal("1.231"),
        bid=Decimal("1.230"),
        ask=Decimal("1.231"),
        bid_size=120000,
        ask_size=95000,
        volume=1829300,
        turnover=Decimal("2251330.00"),
    )
    defaults.update(overrides)
    return MarketQuote(**defaults)


def _bar(**overrides) -> Bar:
    defaults = dict(
        symbol="159852",
        exchange=Exchange.SZSE,
        timeframe="1m",
        timestamp=TUE_AM,
        open=Decimal("1.230"),
        high=Decimal("1.236"),
        low=Decimal("1.229"),
        close=Decimal("1.231"),
        volume=1829300,
        turnover=Decimal("2251330.00"),
        is_closed=True,
    )
    defaults.update(overrides)
    return Bar(**defaults)


def _q(status: str = "FRESH", tradable: bool = True) -> dict:
    return {
        "status": status,
        "tradable": tradable,
        "reasons": [],
        "quote_age_ms": 120,
    }


def _feed(
    *,
    now: datetime = TUE_AM,
    quotes: dict | None = None,
    quality: dict | None = None,
    bars: dict | None = None,
    bar_service=None,
    cache=None,
    config: PaperFeedConfig | None = None,
    instruments=None,
) -> PaperMarketFeed:
    """Paper feed wired to fakes — never touches the real pipeline."""
    return PaperMarketFeed(
        config=config,
        quote_service=FakeQuoteService(quotes, quality),
        bar_service=(
            bar_service if bar_service is not None else FakeBarService(bars)
        ),
        merge_engine=None,          # realtime-only unless a test says otherwise
        market_cache=cache,
        instrument_master=instruments,
        clock=FakeClock(now),
    )


def _live_feed(**kwargs) -> PaperMarketFeed:
    """Feed with a fresh quote + FRESH quality for 159852."""
    kwargs.setdefault("quotes", {"159852": _quote()})
    kwargs.setdefault("quality", {"159852": _q()})
    return _feed(**kwargs)


# ══════════════════════════════════════════════════════════════════
# Market Feed (§2 / §16 / §19)
# ══════════════════════════════════════════════════════════════════
def test_subscribe_accepts_the_full_11_symbol_universe():
    feed = _feed()
    subscribed = feed.subscribe(universe.enabled())
    assert len(subscribed) == 11
    assert set(feed.subscriptions()) == {i.symbol for i in universe.all()}
    assert "159852" in feed.subscriptions()
    assert "165520" in feed.subscriptions()


def test_subscribe_accepts_bare_codes():
    feed = _feed()
    feed.subscribe(["159852", "159559", "159890"])
    assert feed.subscriptions() == ["159852", "159559", "159890"]
    assert feed.subscribed("159559") is True
    assert feed.subscribed("513050") is False


def test_subscribe_rejects_unknown_symbol():
    feed = _feed()
    with pytest.raises(PaperBlockedError) as exc:
        feed.subscribe(["159852", "999999"])
    assert exc.value.code is PaperFeedError.MARKET_DATA_UNAVAILABLE
    assert "999999" in exc.value.symbol
    # nothing was registered — the whole call is atomic
    assert feed.subscriptions() == []


def test_subscribe_is_idempotent_and_unsubscribe_removes():
    feed = _feed()
    feed.subscribe(["159852", "159852"])
    feed.subscribe(["159852"])
    assert feed.subscriptions() == ["159852"]
    assert feed.unsubscribe(["159852"]) == []
    assert feed.subscriptions() == []


def test_get_quote_returns_the_latest_real_quote():
    feed = _live_feed()
    quote = feed.get_quote("159852")
    assert quote.symbol == "159852"
    assert quote.last == Decimal("1.231")
    assert quote.bid == Decimal("1.230")
    assert quote.ask == Decimal("1.231")
    assert quote.bid_size == 120000
    assert quote.ask_size == 95000
    assert quote.volume == 1829300
    assert quote.turnover == Decimal("2251330.00")
    assert quote.timestamp == TUE_AM


def test_get_quote_raises_quote_unavailable():
    feed = _feed()
    with pytest.raises(PaperBlockedError) as exc:
        feed.get_quote("159852")
    assert exc.value.code is PaperFeedError.QUOTE_UNAVAILABLE


def test_latest_quote_returns_none_instead_of_raising():
    assert _feed().latest_quote("159852") is None


def test_get_bar_returns_latest_1m_bar():
    feed = _feed(bars={"159852": [_bar()]})
    bar = feed.get_bar("159852")
    assert isinstance(bar, Bar)
    assert bar.timeframe == "1m"
    assert bar.close == Decimal("1.231")


def test_get_bar_returns_none_without_bars():
    assert _feed().get_bar("159852") is None


def test_get_bar_uses_the_merged_series():
    """§1 — the feed consumes the Commit 008 unified series."""
    bar_service = BarService()
    for minute in range(3):
        bar_service.on_quote(
            _quote(timestamp=TUE_AM + timedelta(minutes=minute))
        )
    engine = BarMergeEngine(
        SyntheticHistoricalProvider(), bar_service=bar_service
    )
    feed = PaperMarketFeed(
        quote_service=FakeQuoteService(),
        bar_service=bar_service,
        merge_engine=engine,
        market_cache=None,
        clock=FakeClock(TUE_AM),
    )
    merged = feed.bars("159852", "1m", limit=10)
    assert merged, "merged series must not be empty"
    assert all(b.symbol == "159852" for b in merged)
    assert all(b.timeframe == "1m" for b in merged)
    # the realtime bars must survive the merge
    assert any(b.timestamp == TUE_AM for b in merged)
    assert feed.get_bar("159852") is not None


def test_get_bar_as_of_never_returns_a_future_bucket():
    """§7 — a bar whose bucket opens after the cutoff is not visible."""
    bar_service = BarService()
    for minute in range(3):
        bar_service.on_quote(
            _quote(timestamp=TUE_AM + timedelta(minutes=minute))
        )
    engine = BarMergeEngine(
        SyntheticHistoricalProvider(), bar_service=bar_service
    )
    feed = PaperMarketFeed(
        quote_service=FakeQuoteService(),
        bar_service=bar_service,
        merge_engine=engine,
        market_cache=None,
        clock=FakeClock(TUE_AM),
    )
    cutoff = TUE_AM + timedelta(seconds=30)
    bars = feed.bars("159852", "1m", limit=50, as_of=cutoff)
    assert bars
    assert all(b.timestamp <= cutoff for b in bars)


def test_stream_yields_quotes_for_subscribed_symbols():
    feed = _feed(
        quotes={
            "159852": _quote(),
            "159559": _quote(symbol="159559", last=Decimal("2.100")),
        }
    )
    got = list(
        feed.stream(
            ["159852", "159559"],
            timeout=0.5,
            poll_interval=0.01,
            max_quotes=2,
        )
    )
    assert len(got) == 2
    assert {q.symbol for q in got} == {"159852", "159559"}


def test_stream_without_subscriptions_yields_nothing():
    assert list(_feed().stream([], timeout=0.2)) == []


# ══════════════════════════════════════════════════════════════════
# Quality Gate is a hard gate (§10 / §19)
# ══════════════════════════════════════════════════════════════════
def test_quality_fresh_allows_the_order():
    feed = _live_feed()
    decision = feed.check_order("159852", quantity=200)
    assert decision.allowed is True
    assert decision.reason is None
    assert decision.quality == "FRESH"


def test_quality_warning_blocks_by_default():
    feed = _live_feed(quality={"159852": _q("WARNING", False)})
    decision = feed.check_order("159852", quantity=200)
    assert decision.allowed is False
    assert decision.reason == PaperFeedError.MARKET_DATA_WARNING.value
    assert decision.quality == "WARNING"


def test_quality_warning_allows_when_explicitly_configured():
    feed = _live_feed(
        quality={"159852": _q("WARNING", False)},
        config=PaperFeedConfig(allow_warning_trading=True),
    )
    assert feed.check_order("159852", quantity=200).allowed is True


def test_quality_stale_blocks():
    feed = _live_feed(quality={"159852": _q("STALE", False)})
    decision = feed.check_order("159852", quantity=200)
    assert decision.allowed is False
    assert decision.reason == PaperFeedError.MARKET_DATA_STALE.value


def test_quality_invalid_blocks():
    feed = _live_feed(quality={"159852": _q("INVALID", False)})
    decision = feed.check_order("159852", quantity=200)
    assert decision.allowed is False
    assert decision.reason == PaperFeedError.MARKET_DATA_INVALID.value


def test_quality_quarantined_blocks():
    feed = _live_feed(quality={"159852": _q("QUARANTINED", False)})
    decision = feed.check_order("159852", quantity=200)
    assert decision.allowed is False
    assert decision.reason == PaperFeedError.MARKET_DATA_INVALID.value
    # the exact status is preserved so a QUARANTINED block stays
    # distinguishable from an INVALID one in the audit trail
    assert decision.quality == "QUARANTINED"


def test_old_quote_is_derived_as_stale_and_blocks():
    """Read-path derivation (no write-path gate) still blocks."""
    stale_quote = _quote(timestamp=TUE_AM - timedelta(minutes=15))
    feed = _feed(quotes={"159852": stale_quote})   # quality map empty
    view = feed.get_quality("159852")
    assert view is not None
    assert view["status"] != "FRESH"
    assert view["tradable"] is False
    assert feed.check_order("159852", quantity=200).allowed is False


# ══════════════════════════════════════════════════════════════════
# Trading Session is a hard gate (§11 / §19)
# ══════════════════════════════════════════════════════════════════
def test_calendar_phases_match_the_fixture_timestamps():
    """Guard the fixture itself: the phases below are what we claim."""
    assert calendar.get_session(TUE_AM).phase.value == "CONTINUOUS_AM"
    assert calendar.get_session(TUE_LUNCH).phase.value == "LUNCH_BREAK"
    assert calendar.get_session(TUE_PM).phase.value == "CONTINUOUS_PM"
    assert calendar.get_session(TUE_CLOSE).phase.value == "CLOSE"
    assert calendar.get_session(TUE_POST).phase.value == "POST_CLOSE"
    assert calendar.get_session(SUN_NOON).phase.value == "NON_TRADING"


@pytest.mark.parametrize("at", [TUE_AM, TUE_PM])
def test_session_continuous_phases_allow(at):
    feed = _live_feed(now=at, quotes={"159852": _quote(timestamp=at)})
    decision = feed.check_order("159852", quantity=200)
    assert decision.allowed is True


@pytest.mark.parametrize(
    "at,phase",
    [
        (TUE_LUNCH, "LUNCH_BREAK"),
        (TUE_CLOSE, "CLOSE"),
        (TUE_POST, "POST_CLOSE"),
        (SUN_NOON, "NON_TRADING"),
    ],
)
def test_session_closed_phases_block(at, phase):
    feed = _live_feed(now=at)
    decision = feed.check_order("159852", quantity=200)
    assert decision.allowed is False
    assert decision.reason == PaperFeedError.SESSION_BLOCKED.value


@pytest.mark.parametrize("at", [TUE_LUNCH, TUE_CLOSE, SUN_NOON])
def test_session_gate_beats_quality_gate(at):
    """A closed market is not a data-quality problem — the reason
    code must say SESSION_BLOCKED, not a quality code."""
    feed = _live_feed(now=at)
    assert (
        feed.check_order("159852", quantity=200).reason
        == PaperFeedError.SESSION_BLOCKED.value
    )


# ══════════════════════════════════════════════════════════════════
# Fill pricing (§5 / §6 / §9 / §19)
# ══════════════════════════════════════════════════════════════════
def test_buy_fills_at_ask():
    feed = _live_feed()
    price, source = feed.fill_price("159852", "BUY")
    assert price == Decimal("1.231")
    assert source is FillPriceSource.ASK


def test_sell_fills_at_bid():
    feed = _live_feed()
    price, source = feed.fill_price("159852", "SELL")
    assert price == Decimal("1.230")
    assert source is FillPriceSource.BID


@pytest.mark.parametrize("side", ["BUY", "SELL"])
def test_fill_falls_back_to_last_without_a_book(side):
    feed = _live_feed(
        quotes={
            "159852": _quote(
                last=Decimal("1.225"),
                bid=Decimal("0"),
                ask=Decimal("0"),
                bid_size=0,
                ask_size=0,
            )
        }
    )
    price, source = feed.fill_price("159852", side)
    assert price == Decimal("1.225")
    assert source is FillPriceSource.LAST


def test_slippage_is_applied_to_both_sides():
    feed = _live_feed(config=PaperFeedConfig(slippage_bps=10.0))  # 0.10%
    buy, buy_src = feed.fill_price("159852", "BUY")
    sell, sell_src = feed.fill_price("159852", "SELL")
    assert buy == Decimal("1.231") * Decimal("1.001")
    assert sell == Decimal("1.230") * Decimal("0.999")
    assert buy_src is FillPriceSource.ASK
    assert sell_src is FillPriceSource.BID


def test_default_slippage_is_zero():
    assert PaperFeedConfig().slippage_bps == 0.0
    assert _live_feed().config.slippage_bps == 0.0


def test_unsupported_side_is_rejected():
    feed = _live_feed()
    with pytest.raises(ValueError):
        feed.fill_price("159852", "HOLD")


def test_fill_records_price_source_and_timestamps():
    """§9 — Signal BUY 159852 200 → fill @ 1.231 (the ASK)."""
    feed = _live_feed()
    fill = feed.fill("159852", "BUY", 200)
    assert fill.price == Decimal("1.231")
    assert fill.price_source == "ASK"
    assert fill.quantity == 200
    assert fill.notional == Decimal("1.231") * 200
    assert fill.quote_timestamp == TUE_AM
    assert fill.fill_timestamp >= fill.order_timestamp


def test_fill_raises_through_the_block_reason():
    feed = _live_feed(quality={"159852": _q("STALE", False)})
    with pytest.raises(PaperBlockedError) as exc:
        feed.fill("159852", "BUY", 200)
    assert exc.value.code is PaperFeedError.MARKET_DATA_STALE


def test_preview_fill_exposes_the_price_when_allowed():
    feed = _live_feed()
    decision = feed.preview_fill("159852", "SELL", 100)
    assert decision.allowed is True
    assert decision.fill_price == Decimal("1.230")
    assert decision.fill_price_source == "BID"


# ══════════════════════════════════════════════════════════════════
# Risk / Integrity (§7 / §8 / §12 / §17 / §19)
# ══════════════════════════════════════════════════════════════════
@pytest.mark.parametrize("quantity", [100, 200, 300, 1000])
def test_valid_lot_sizes_are_allowed(quantity):
    feed = _live_feed()
    assert feed.check_order("159852", quantity=quantity).allowed is True


@pytest.mark.parametrize("quantity", [150, 1, 50, 0, -100])
def test_invalid_lot_size_blocks(quantity):
    feed = _live_feed()
    decision = feed.check_order("159852", quantity=quantity)
    assert decision.allowed is False
    assert decision.reason == PaperFeedError.INVALID_LOT_SIZE.value


def test_lot_size_comes_from_the_instrument_master_not_a_literal():
    """§8 — nothing in the feed hard-codes 100."""
    feed = _live_feed(instruments=FakeInstruments(lot_size=1))
    assert feed.check_order("159852", quantity=1).allowed is True
    assert feed.check_order("159852", quantity=7).allowed is True

    feed10 = _live_feed(instruments=FakeInstruments(lot_size=10))
    assert feed10.check_order("159852", quantity=10).allowed is True
    assert feed10.check_order("159852", quantity=100).allowed is True
    assert feed10.check_order("159852", quantity=15).allowed is False


def test_lot_size_gate_can_be_disabled():
    feed = _live_feed(
        instruments=FakeInstruments(lot_size=100),
        config=PaperFeedConfig(enforce_lot_size=False),
    )
    assert feed.check_order("159852", quantity=150).allowed is True


def test_lookahead_violation_blocks():
    """§7 — a quote that arrived after the order must never fill it."""
    arrived = TUE_AM + timedelta(seconds=5)
    feed = _live_feed(
        now=TUE_AM + timedelta(seconds=10),
        quotes={"159852": _quote(received_timestamp=arrived)},
    )
    decision = feed.check_order(
        "159852", side="BUY", quantity=200, order_timestamp=TUE_AM
    )
    assert decision.allowed is False
    assert decision.reason == PaperFeedError.LOOKAHEAD_VIOLATION.value


def test_get_quote_with_as_of_rejects_future_arrival():
    arrived = TUE_AM + timedelta(seconds=5)
    feed = _live_feed(
        now=TUE_AM + timedelta(seconds=10),
        quotes={"159852": _quote(received_timestamp=arrived)},
    )
    with pytest.raises(PaperBlockedError) as exc:
        feed.get_quote("159852", as_of=TUE_AM)
    assert exc.value.code is PaperFeedError.LOOKAHEAD_VIOLATION
    # the same quote is perfectly fine once it has actually arrived
    assert feed.get_quote("159852", as_of=arrived) is not None


def test_lookahead_tolerance_allows_small_clock_skew():
    feed = _live_feed(
        now=TUE_AM + timedelta(seconds=1),
        quotes={"159852": _quote(received_timestamp=TUE_AM + timedelta(seconds=1))},
        config=PaperFeedConfig(lookahead_tolerance_ms=2000),
    )
    assert (
        feed.check_order(
            "159852", side="BUY", quantity=200, order_timestamp=TUE_AM
        ).allowed
        is True
    )


def test_future_quote_blocks_as_invalid():
    feed = _live_feed(
        quotes={"159852": _quote(timestamp=TUE_AM + timedelta(minutes=5))}
    )
    decision = feed.check_order("159852", quantity=200)
    assert decision.allowed is False
    assert decision.reason == PaperFeedError.MARKET_DATA_INVALID.value


def test_redis_degraded_blocks_new_orders():
    """§12 — a failing cache must never let Paper Trading trade blind."""
    feed = _live_feed(cache=FakeCache(degraded=True))
    decision = feed.check_order("159852", quantity=200)
    assert decision.allowed is False
    assert decision.reason == PaperFeedError.FEED_DEGRADED.value
    # §5 — the quote itself is fine, only new orders are held back
    assert feed.get_quote("159852") is not None


def test_degraded_cache_is_ignored_when_not_required():
    feed = _live_feed(
        cache=FakeCache(degraded=True),
        config=PaperFeedConfig(require_healthy_cache=False),
    )
    assert feed.check_order("159852", quantity=200).allowed is True


def test_every_block_records_a_machine_readable_reason():
    """§17 — a block is never a bare False."""
    scenarios = [
        _feed(),
        _live_feed(quality={"159852": _q("STALE", False)}),
        _live_feed(quality={"159852": _q("INVALID", False)}),
        _live_feed(quality={"159852": _q("QUARANTINED", False)}),
        _live_feed(now=TUE_LUNCH),
        _live_feed(cache=FakeCache(degraded=True)),
        _live_feed(bars=None, quotes={"159852": _quote(timestamp=TUE_AM + timedelta(minutes=5))}),
    ]
    valid = {e.value for e in PaperFeedError}
    for feed in scenarios:
        decision = feed.check_order("159852", quantity=200)
        assert decision.allowed is False
        assert decision.reason in valid
        payload = decision.as_dict()
        assert payload["reason"] == decision.reason
        assert payload["symbol"] == "159852"


def test_block_decision_payload_matches_the_spec_shape():
    feed = _live_feed(quality={"159852": _q("STALE", False)})
    payload = feed.check_order("159852", quantity=200).as_dict()
    assert payload["allowed"] is False
    assert payload["reason"] == "PAPER_MARKET_DATA_STALE"
    assert payload["symbol"] == "159852"
    assert isinstance(payload["quote_age_ms"], int)


def test_blocked_decisions_are_counted_in_stats():
    feed = _live_feed(quality={"159852": _q("STALE", False)})
    feed.check_order("159852", quantity=200)
    feed.check_order("159852", quantity=200)
    stats = feed.stats()
    assert (
        stats["blocked_by_reason"][PaperFeedError.MARKET_DATA_STALE.value] == 2
    )


# ══════════════════════════════════════════════════════════════════
# Feed state (§12 / §14 / §19)
# ══════════════════════════════════════════════════════════════════
def test_state_offline_without_subscriptions():
    assert _live_feed().state is PaperFeedState.OFFLINE


def test_state_offline_when_the_feed_is_disabled():
    feed = _live_feed(config=PaperFeedConfig(enabled=False))
    feed.subscribe(["159852"])
    assert feed.state is PaperFeedState.OFFLINE


def test_state_offline_when_no_quote_has_arrived():
    feed = _feed()
    feed.subscribe(["159852"])
    assert feed.state is PaperFeedState.OFFLINE


def test_state_ready_when_open_fresh_and_healthy():
    feed = _live_feed(cache=FakeCache())
    feed.subscribe(["159852"])
    assert feed.state is PaperFeedState.READY
    assert feed.ready is True


def test_state_degraded_when_the_cache_is_failing():
    feed = _live_feed(cache=FakeCache(degraded=True))
    feed.subscribe(["159852"])
    assert feed.state is PaperFeedState.DEGRADED


def test_state_blocked_outside_the_trading_session():
    feed = _live_feed(now=TUE_LUNCH)
    feed.subscribe(["159852"])
    assert feed.state is PaperFeedState.BLOCKED


def test_state_blocked_when_quality_is_not_fresh():
    feed = _live_feed(quality={"159852": _q("STALE", False)})
    feed.subscribe(["159852"])
    assert feed.state is PaperFeedState.BLOCKED


# ══════════════════════════════════════════════════════════════════
# Frontend contract (§14 / §15 / §19)
# ══════════════════════════════════════════════════════════════════
def test_disclaimer_is_unambiguous():
    assert DISCLAIMER == "PAPER — NO REAL MONEY"
    assert _live_feed().disclaimer == DISCLAIMER


def test_status_exposes_the_paper_badge_and_never_lies_about_money():
    feed = _live_feed(cache=FakeCache())
    feed.subscribe(["159852"])
    status = feed.status()
    assert status["environment"] == "PAPER"
    assert status["disclaimer"] == "PAPER — NO REAL MONEY"
    assert status["state"] == "READY"
    assert status["instruments"] == 1
    assert status["tradable"] == 1
    assert status["blocked"] == 0


def test_status_exposes_market_quote_and_quality():
    feed = _live_feed(cache=FakeCache())
    feed.subscribe(["159852"])
    status = feed.status()
    # market status (§14 "Market: OPEN")
    assert status["market"]["phase"] == "CONTINUOUS_AM"
    assert status["market"]["is_tradable"] is True
    assert status["market"]["trading_date"] == "2026-09-08"
    row = status["rows"][0]
    # quote status
    assert row["last"] == "1.231"
    assert row["bid"] == "1.230"
    assert row["ask"] == "1.231"
    assert isinstance(row["quote_age_ms"], int)
    # quality status
    assert row["quality"] == "FRESH"
    # paper order status
    assert row["tradable"] is True
    assert row["blocked_reason"] is None
    assert row["fill_price_source"] == "ASK"
    assert row["lot_size"] == 100


def test_status_reports_the_block_reason_per_symbol():
    feed = _live_feed(quality={"159852": _q("STALE", False)})
    feed.subscribe(["159852"])
    status = feed.status()
    assert status["state"] == "BLOCKED"
    assert status["tradable"] == 0
    assert status["blocked"] == 1
    assert status["rows"][0]["blocked_reason"] == "PAPER_MARKET_DATA_STALE"


def test_status_reports_a_degraded_cache():
    feed = _live_feed(cache=FakeCache(degraded=True))
    feed.subscribe(["159852"])
    status = feed.status()
    assert status["state"] == "DEGRADED"
    assert status["cache"]["state"] == "DEGRADED"


# ══════════════════════════════════════════════════════════════════
# PaperTradingSession integration (§9 / §13 / §19)
# ══════════════════════════════════════════════════════════════════
def test_adapter_quote_returns_the_mid_price():
    adapter = PaperMarketFeedAdapter(_live_feed())
    # (1.230 + 1.231) / 2 = 1.2305
    assert adapter.quote("159852") == pytest.approx(1.2305)
    assert adapter.last_error is None


def test_adapter_quote_falls_back_when_unavailable():
    adapter = PaperMarketFeedAdapter(_feed(), fallback_price=0.0)
    assert adapter.quote("159852") == 0.0
    assert adapter.last_error == PaperFeedError.QUOTE_UNAVAILABLE.value
    assert adapter.disclaimer == DISCLAIMER


def test_adapter_fill_price_is_book_aware():
    adapter = PaperMarketFeedAdapter(_live_feed())
    assert adapter.fill_price("159852", "BUY") == pytest.approx(1.231)
    assert adapter.fill_price("159852", "SELL") == pytest.approx(1.230)
    price, source = adapter.fill_price_with_source("159852", "BUY")
    assert price == pytest.approx(1.231)
    assert source is FillPriceSource.ASK


def test_real_market_session_fills_at_the_ask():
    """§9 — Signal BUY 159852 200 with Bid 1.230 / Ask 1.231 → 1.231."""
    adapter = PaperMarketFeedAdapter(_live_feed())
    session = RealMarketPaperSession(adapter, account=PaperAccount())
    record = session.process(SignalSpec(symbol="159852", side="BUY", quantity=200))
    assert record.get("rejected") is None
    position = session.account.positions["159852"]
    assert position["quantity"] == 200
    assert position["avg_price"] == pytest.approx(1.231)


def test_real_market_session_blocks_an_invalid_lot_size():
    adapter = PaperMarketFeedAdapter(_live_feed())
    session = RealMarketPaperSession(adapter, account=PaperAccount())
    record = session.process(SignalSpec(symbol="159852", side="BUY", quantity=150))
    assert record["rejected"] is True
    assert record["reason"] == PaperFeedError.INVALID_LOT_SIZE.value
    assert session.account.positions == {}
    assert len(session.blocked_decisions()) == 1


def test_real_market_session_refuses_to_fill_outside_the_session():
    adapter = PaperMarketFeedAdapter(_live_feed(now=TUE_LUNCH))
    session = RealMarketPaperSession(adapter, account=PaperAccount())
    record = session.process(SignalSpec(symbol="159852", side="BUY", quantity=200))
    assert record["rejected"] is True
    assert record["reason"] == PaperFeedError.SESSION_BLOCKED.value


def test_real_market_session_report_marks_paper_and_no_real_money():
    adapter = PaperMarketFeedAdapter(_live_feed(cache=FakeCache()))
    session = RealMarketPaperSession(adapter, account=PaperAccount())
    session.process(SignalSpec(symbol="159852", side="BUY", quantity=200))
    report = session.report()
    assert report["mode"] == "paper"
    assert report["environment"] == "PAPER"
    assert report["disclaimer"] == "PAPER — NO REAL MONEY"
    assert report["positions"]["159852"]["quantity"] == 200
    assert report["feed_state"] == "OFFLINE"  # nothing subscribed yet
    assert report["blocked_orders"] == 0


def test_real_market_session_does_not_invent_rejections():
    """Unlike the legacy random profile, a real-data session with
    clean data must fill every valid signal."""
    adapter = PaperMarketFeedAdapter(_live_feed())
    session = RealMarketPaperSession(adapter, account=PaperAccount())
    session.run(
        [
            SignalSpec(symbol="159852", side="BUY", quantity=100),
            SignalSpec(symbol="159852", side="BUY", quantity=100),
        ]
    )
    summary = session.metrics.summary()
    assert summary["signals"] == 2
    assert summary["fill_rate_pct"] == 100.0
    assert summary["reject_rate_pct"] == 0.0


def test_slippage_config_flows_into_the_session_fill():
    feed = _live_feed(config=PaperFeedConfig(slippage_bps=10.0))
    adapter = PaperMarketFeedAdapter(feed)
    session = RealMarketPaperSession(adapter, account=PaperAccount())
    session.process(SignalSpec(symbol="159852", side="BUY", quantity=200))
    # 1.231 * 1.001
    assert session.account.positions["159852"]["avg_price"] == pytest.approx(
        1.232231
    )
