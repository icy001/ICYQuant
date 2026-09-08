"""Tests for the Market Cache — the shared latest market state (Commit 007).

Gate: Redis key convention (§4), quote/bar/session/quality round trips
(§5), atomic single-key updates (§9), timestamp protection (§10), TTL
zombie-quote prevention (§6), session-aware TTL (§7), the honest
CacheState verdict (quote age + trading session, §7), failure
degradation (§14/§15 — DEGRADED blocks the trading path while
ingestion keeps retrying) and the QuoteFeed → cache write path.
"""
from __future__ import annotations

import fnmatch
import time
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from services.market_data.adapters.mock import MockMarketDataAdapter
from services.market_data.aggregation.bar_service import BarService
from services.market_data.cache import (
    CacheBackendError,
    CacheConfig,
    CacheState,
    MarketCache,
    bar_key,
    quote_key,
    quote_pattern,
    quality_key,
    session_key,
)
from services.market_data.cache.redis_keys import NAMESPACE
from services.market_data.calendar.trading_calendar import calendar
from services.market_data.domain.bar import Bar
from services.market_data.domain.instrument import Exchange
from services.market_data.domain.quote import MarketQuote
from services.market_data.quality.quality_config import QualityConfig
from services.market_data.quote_service import QuoteFeed, QuoteService
from services.market_data.validators.market_data_validator import (
    MarketDataValidator,
)

# ── deterministic timestamps (CST wall-clock in UTC form) ──────────
# 2026-09-08 is a Tuesday and a trading day (see calendar tests).
TUE_AM = datetime(2026, 9, 8, 2, 45, tzinfo=timezone.utc)   # 10:45 CONTINUOUS_AM
TUE_LUNCH = datetime(2026, 9, 8, 3, 45, tzinfo=timezone.utc)  # 11:45 LUNCH_BREAK
TUE_POST = datetime(2026, 9, 8, 7, 30, tzinfo=timezone.utc)  # 15:30 POST_CLOSE
SUN_NOON = datetime(2026, 9, 6, 4, 0, tzinfo=timezone.utc)   # 12:00 Sunday


class FakeClock:
    """Mutable clock — deterministic TTL / age arithmetic."""

    def __init__(self, now: datetime) -> None:
        self.now = now

    def __call__(self) -> datetime:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += timedelta(seconds=seconds)


def _quote(**overrides) -> MarketQuote:
    defaults = dict(
        symbol="159852",
        exchange=Exchange.SZSE,
        timestamp=TUE_AM,
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


def _bar(**overrides) -> Bar:
    defaults = dict(
        symbol="159852",
        exchange=Exchange.SZSE,
        timeframe="1m",
        timestamp=TUE_AM,
        open=Decimal("1.230"),
        high=Decimal("1.240"),
        low=Decimal("1.220"),
        close=Decimal("1.235"),
        volume=100,
        turnover=Decimal("123.50"),
        is_closed=True,
    )
    defaults.update(overrides)
    return Bar(**defaults)


def _cache(now: datetime, **cfg) -> MarketCache:
    config = CacheConfig(enabled=True, redis_url=None, **cfg)
    return MarketCache(
        config=config,
        quality_config=QualityConfig(),
        clock=FakeClock(now),
    )


class FlakyBackend:
    """Test double: toggled CacheBackendError on every operation."""

    name = "flaky"

    def __init__(self) -> None:
        self.fail = False
        self._mem: dict[str, str] = {}

    def _check(self) -> None:
        if self.fail:
            raise CacheBackendError("backend unavailable")

    def get(self, key):
        self._check()
        return self._mem.get(key)

    def set(self, key, value, ttl_seconds):
        self._check()
        self._mem[key] = value

    def delete(self, key):
        self._check()
        self._mem.pop(key, None)

    def keys(self, pattern):
        self._check()
        return [k for k in self._mem if fnmatch.fnmatch(k, pattern)]

    def ping(self) -> bool:
        self._check()
        return True

    def clear(self) -> None:
        self._mem.clear()


# ── §4 Redis key convention ────────────────────────────────────────


class TestKeyConvention:
    def test_keys_match_spec(self):
        assert quote_key("159852") == "icyquant:market:quote:159852"
        assert bar_key("1m", "159852") == "icyquant:market:bar:1m:159852"
        assert session_key("SZSE") == "icyquant:market:session:SZSE"
        assert quality_key("159852") == "icyquant:market:quality:159852"

    def test_pattern_matches_every_quote_key(self):
        pattern = quote_pattern()
        assert pattern == "icyquant:market:quote:*"
        assert fnmatch.fnmatch(quote_key("159852"), pattern)
        assert fnmatch.fnmatch(quote_key("513050"), pattern)
        assert not fnmatch.fnmatch(bar_key("1m", "159852"), pattern)
        assert not fnmatch.fnmatch(quality_key("159852"), pattern)
        assert NAMESPACE == "icyquant:market"

    def test_symbols_inventory(self):
        cache = _cache(TUE_AM)
        cache.set_quote(_quote())
        cache.set_quote(_quote(symbol="513050"))
        assert cache.symbols() == ["159852", "513050"]


# ── §5 quote / bar / session / quality round trips ─────────────────


class TestQuoteCache:
    def test_round_trip_latest_quote(self):
        cache = _cache(TUE_AM)
        assert cache.set_quote(_quote()) is True
        entry = cache.get_quote("159852")
        assert entry is not None
        for field in (
            "symbol", "exchange", "timestamp", "last", "bid", "ask",
            "bid_size", "ask_size", "volume", "turnover", "quality_status",
            "cached_at", "ts_ms", "ttl_seconds",
        ):
            assert field in entry, f"missing {field}"
        assert entry["symbol"] == "159852"
        assert entry["exchange"] == "SZSE"
        assert entry["last"] == "1.234"

    def test_unknown_symbol_is_miss(self):
        cache = _cache(TUE_AM)
        assert cache.get_quote("999999") is None

    def test_quality_verdict_cached_alongside(self):
        cache = _cache(TUE_AM)
        quality = {"symbol": "159852", "status": "FRESH", "passed": True}
        assert cache.set_quote(_quote(), quality=quality) is True
        # the quote entry is tagged with the verdict
        assert cache.get_quote("159852")["quality_status"] == "FRESH"
        # and the full verdict lives under the quality key
        cached = cache.get_quality("159852")
        assert cached is not None
        assert cached["status"] == "FRESH"
        assert cached["symbol"] == "159852"

    def test_quality_symbol_filled_from_quote(self):
        cache = _cache(TUE_AM)
        # a verdict dict without a symbol still stores — the symbol
        # falls back to the quote's own symbol
        assert cache.set_quote(_quote(), quality={"status": "FRESH"}) is True
        assert cache.get_quote("159852")["quality_status"] == "FRESH"
        assert cache.get_quality("159852")["symbol"] == "159852"

    def test_session_refreshed_on_quote_write(self):
        cache = _cache(TUE_AM)
        assert cache.set_quote(_quote()) is True
        session = cache.get_session("SZSE")
        assert session is not None
        assert session["phase"] == "CONTINUOUS_AM"
        assert session["is_trading_day"] is True

    def test_stats_count_writes(self):
        cache = _cache(TUE_AM)
        cache.set_quote(_quote())
        cache.set_quote(_quote(symbol="513050"))
        stats = cache.stats()
        assert stats["writes"]["quote"] == 2
        assert stats["writes"]["session"] == 1  # written once, not per tick
        assert stats["writes"]["quality"] == 0
        assert stats["write_failures"] == 0


class TestBarCache:
    def test_round_trip_latest_bar(self):
        cache = _cache(TUE_AM)
        assert cache.set_bar(_bar()) is True
        bar = cache.get_latest_bar("159852")
        assert bar is not None
        for field in (
            "symbol", "timeframe", "timestamp", "open", "high", "low",
            "close", "volume", "turnover", "is_closed",
        ):
            assert field in bar, f"missing {field}"
        assert bar["timeframe"] == "1m"
        assert bar["is_closed"] is True

    def test_unknown_symbol_is_miss(self):
        cache = _cache(TUE_AM)
        assert cache.get_latest_bar("999999") is None


class TestSessionQualityCache:
    def test_session_round_trip(self):
        cache = _cache(TUE_AM)
        session = calendar.get_session(TUE_AM)
        assert cache.set_session(session) is True
        cached = cache.get_session("SZSE")
        assert cached["phase"] == "CONTINUOUS_AM"
        assert cached["is_tradable"] is True
        assert cached["trading_date"] == "2026-09-08"

    def test_quality_round_trip(self):
        cache = _cache(TUE_AM)
        verdict = {
            "symbol": "159852", "status": "STALE", "passed": False,
            "tradable": False,
        }
        assert cache.set_quality(verdict) is True
        cached = cache.get_quality("159852")
        assert cached["status"] == "STALE"
        assert cached["tradable"] is False


# ── §9 atomic update ──────────────────────────────────────────────


class TestAtomicUpdate:
    def test_single_key_per_symbol(self):
        cache = _cache(TUE_AM)
        for i in range(5):
            cache.set_quote(
                _quote(timestamp=TUE_AM + timedelta(seconds=i))
            )
        assert cache.symbols() == ["159852"]  # one key, replaced 5x
        assert cache.get_quote("159852")["volume"] == 1000000

    def test_fields_switch_together(self):
        """A quote is one complete object — never a stitched state."""
        cache = _cache(TUE_AM)
        t_b = TUE_AM + timedelta(seconds=1)
        cache.set_quote(
            _quote(timestamp=TUE_AM, last=Decimal("1.100"), volume=100)
        )
        cache.set_quote(
            _quote(timestamp=t_b, last=Decimal("1.200"), volume=200)
        )
        entry = cache.get_quote("159852")
        assert entry["last"] == "1.200"
        assert entry["volume"] == 200
        assert entry["timestamp"] == t_b.isoformat()

    def test_bar_replaces_atomically(self):
        cache = _cache(TUE_AM)
        t1 = TUE_AM
        t2 = TUE_AM + timedelta(minutes=1)
        cache.set_bar(_bar(timestamp=t1, close=Decimal("1.230")))
        cache.set_bar(_bar(timestamp=t2, close=Decimal("1.240")))
        bar = cache.get_latest_bar("159852")
        assert bar["close"] == "1.240"
        assert bar["timestamp"] == t2.isoformat()


# ── §10 timestamp protection ───────────────────────────────────────


class TestTimestampProtection:
    def test_older_quote_never_overwrites_newer(self):
        """Network reordering: B arrives first, A must not land after."""
        cache = _cache(TUE_AM)
        t_b = TUE_AM + timedelta(seconds=1)
        assert cache.set_quote(_quote(timestamp=t_b, last=Decimal("1.200"))) is True
        # the older A arrives late
        assert cache.set_quote(_quote(timestamp=TUE_AM, last=Decimal("1.100"))) is False
        entry = cache.get_quote("159852")
        assert entry["last"] == "1.200"
        assert entry["timestamp"] == t_b.isoformat()

    def test_stale_update_counted(self):
        cache = _cache(TUE_AM)
        cache.set_quote(_quote(timestamp=TUE_AM + timedelta(seconds=1)))
        cache.set_quote(_quote(timestamp=TUE_AM))
        cache.set_quote(_quote(timestamp=TUE_AM - timedelta(seconds=5)))
        assert cache.stats()["stale_updates_rejected"] == 2

    def test_equal_timestamp_allowed(self):
        """Equal timestamps (tick updates within one ms) are not older."""
        cache = _cache(TUE_AM)
        cache.set_quote(_quote(timestamp=TUE_AM, last=Decimal("1.100")))
        assert cache.set_quote(_quote(timestamp=TUE_AM, last=Decimal("1.111"))) is True
        assert cache.get_quote("159852")["last"] == "1.111"

    def test_older_bar_never_overwrites_newer(self):
        cache = _cache(TUE_AM)
        t_new = TUE_AM
        t_old = TUE_AM - timedelta(minutes=3)
        assert cache.set_bar(_bar(timestamp=t_new, close=Decimal("1.235"))) is True
        assert cache.set_bar(_bar(timestamp=t_old, close=Decimal("1.100"))) is False
        assert cache.get_latest_bar("159852")["close"] == "1.235"


# ── §6 TTL — no zombie quotes ─────────────────────────────────────


class TestTtlExpiry:
    def test_quote_expires_to_miss(self):
        clock = FakeClock(TUE_AM)
        cache = MarketCache(
            config=CacheConfig(enabled=True, ttl_trading_s=10,
                               ttl_closed_s=20),
            quality_config=QualityConfig(),
            clock=clock,
        )
        assert cache.set_quote(_quote(timestamp=TUE_AM)) is True
        assert cache.get_quote("159852") is not None
        clock.advance(11)  # beyond the trading TTL
        assert cache.get_quote("159852") is None  # no zombie quote
        assert cache.cache_state("159852") is CacheState.MISS

    def test_bar_and_quality_expire(self):
        clock = FakeClock(TUE_AM)
        cache = MarketCache(
            config=CacheConfig(enabled=True, ttl_closed_s=5),
            quality_config=QualityConfig(),
            clock=clock,
        )
        cache.set_bar(_bar())
        cache.set_quality({"symbol": "159852", "status": "FRESH"})
        clock.advance(6)
        assert cache.get_latest_bar("159852") is None
        assert cache.get_quality("159852") is None


# ── §7 session-aware TTL ──────────────────────────────────────────


class TestSessionAwareTtl:
    def test_trading_phase_uses_trading_ttl(self):
        cache = _cache(TUE_AM, ttl_trading_s=3600, ttl_closed_s=86400)
        cache.set_quote(_quote(timestamp=TUE_AM))
        assert cache.get_quote("159852")["ttl_seconds"] == 3600

    def test_lunch_break_uses_closed_ttl(self):
        cache = _cache(TUE_LUNCH, ttl_trading_s=3600, ttl_closed_s=86400)
        cache.set_quote(_quote(timestamp=TUE_LUNCH))
        # lunch is a normal pause — entry must survive the break
        assert cache.get_quote("159852")["ttl_seconds"] == 86400

    def test_post_close_uses_closed_ttl(self):
        cache = _cache(TUE_POST, ttl_trading_s=3600, ttl_closed_s=86400)
        cache.set_quote(_quote(timestamp=TUE_POST))
        assert cache.get_quote("159852")["ttl_seconds"] == 86400

    def test_non_trading_day_uses_closed_ttl(self):
        cache = _cache(SUN_NOON, ttl_trading_s=3600, ttl_closed_s=86400)
        cache.set_quote(_quote(timestamp=SUN_NOON))
        assert cache.get_quote("159852")["ttl_seconds"] == 86400


# ── §7 CacheState: quote age + trading session ────────────────────


class TestCacheState:
    def test_live_during_continuous(self):
        cache = _cache(TUE_AM)
        cache.set_quote(_quote(timestamp=TUE_AM - timedelta(seconds=1)))
        assert cache.cache_state("159852") is CacheState.LIVE

    def test_stale_during_continuous(self):
        """10:45 CONTINUOUS_AM with age 900s — a data problem."""
        cache = _cache(TUE_AM)
        cache.set_quote(_quote(timestamp=TUE_AM - timedelta(seconds=900)))
        assert cache.cache_state("159852") is CacheState.STALE

    def test_paused_during_lunch(self):
        """11:45 LUNCH_BREAK with age 900s — a normal state."""
        cache = _cache(TUE_LUNCH)
        cache.set_quote(_quote(timestamp=TUE_LUNCH - timedelta(seconds=900)))
        assert cache.cache_state("159852") is CacheState.MARKET_PAUSED

    def test_closed_on_non_trading_day(self):
        cache = _cache(SUN_NOON)
        cache.set_quote(_quote(timestamp=SUN_NOON - timedelta(seconds=60)))
        assert cache.cache_state("159852") is CacheState.MARKET_CLOSED

    def test_closed_post_close(self):
        cache = _cache(TUE_POST)
        cache.set_quote(_quote(timestamp=TUE_POST - timedelta(seconds=60)))
        assert cache.cache_state("159852") is CacheState.MARKET_CLOSED

    def test_miss_when_never_written(self):
        cache = _cache(TUE_AM)
        assert cache.cache_state("159852") is CacheState.MISS

    def test_states_are_the_five_spec_values(self):
        assert {s.value for s in CacheState} == {
            "LIVE", "STALE", "MARKET_PAUSED", "MARKET_CLOSED", "MISS",
        }


# ── §13 overview ──────────────────────────────────────────────────


class TestOverview:
    def test_counts_by_state(self):
        cache = _cache(TUE_AM)
        cache.set_quote(
            _quote(symbol="159852", timestamp=TUE_AM - timedelta(seconds=1))
        )
        cache.set_quote(
            _quote(symbol="513050", timestamp=TUE_AM - timedelta(seconds=900))
        )
        ov = cache.overview(["159852", "513050", "159890"])
        assert ov["instruments"] == 3
        assert ov["counts"]["LIVE"] == 1
        assert ov["counts"]["STALE"] == 1
        assert ov["counts"]["MISS"] == 1


# ── §14 / §15 failure degradation ─────────────────────────────────


class TestFailureDegradation:
    def _cache(self, backend: FlakyBackend) -> MarketCache:
        return MarketCache(
            config=CacheConfig(enabled=True),
            backend=backend,
            quality_config=QualityConfig(),
        )

    def test_healthy_then_degraded_then_recovered(self):
        backend = FlakyBackend()
        cache = self._cache(backend)

        # healthy path
        assert cache.set_quote(_quote(timestamp=TUE_AM)) is True
        health = cache.health()
        assert health["status"] == "HEALTHY"
        assert health["trading_allowed"] is True

        # backend dies — writes fail honestly, nothing raises
        backend.fail = True
        newer = _quote(timestamp=TUE_AM + timedelta(seconds=5))
        assert cache.set_quote(newer) is False
        assert cache.get_quote("159852") is None  # read fails → MISS
        health = cache.health()
        assert health["status"] == "DEGRADED"
        assert health["trading_allowed"] is False  # §15 trading path BLOCKED
        assert cache.trading_allowed() is False
        assert health["last_error"]
        assert health["consecutive_failures"] > 0

        # ingestion keeps retrying (§15: the feed itself survives)
        assert cache.set_quote(newer) is False
        assert cache.stats()["write_failures"] >= 2

        # backend heals — the cache recovers without restart
        backend.fail = False
        assert cache.set_quote(newer) is True
        health = cache.health()
        assert health["status"] == "HEALTHY"
        assert health["trading_allowed"] is True

    def test_degraded_cache_never_fakes_success(self):
        backend = FlakyBackend()
        backend.fail = True
        cache = self._cache(backend)
        assert cache.set_quote(_quote(timestamp=TUE_AM)) is False
        assert cache.set_bar(_bar()) is False
        assert cache.set_quality({"symbol": "159852"}) is False
        assert cache.symbols() == []  # inventory read fails → empty


class TestDisabledCache:
    def test_disabled_cache_is_transparent(self):
        cache = MarketCache(
            config=CacheConfig(enabled=False),
            quality_config=QualityConfig(),
        )
        assert cache.set_quote(_quote(timestamp=TUE_AM)) is False
        assert cache.get_quote("159852") is None
        assert cache.cache_state("159852") is CacheState.MISS
        health = cache.health()
        assert health["status"] == "DISABLED"
        # a disabled cache never blocks trading (§15 is about failures)
        assert health["trading_allowed"] is True


# ── E2E: QuoteFeed → quality-passed data → cache ──────────────────


class TestQuoteFeedIntegration:
    def test_feed_populates_cache(self):
        svc = QuoteService(
            validator=MarketDataValidator(stale_seconds=600)
        )
        adapter = MockMarketDataAdapter(seed=7)
        bars = BarService()
        cache = MarketCache(
            config=CacheConfig(enabled=True),
            quality_config=QualityConfig(),
        )
        feed = QuoteFeed(
            adapter, svc, interval=0.01,
            bar_service=bars, market_cache=cache,
        )
        feed.start(symbols=["159852", "513050"])
        deadline = time.time() + 5.0
        while time.time() < deadline:
            if cache.get_quote("159852") and cache.get_quote("513050"):
                break
            time.sleep(0.05)
        feed.stop()

        for sym in ("159852", "513050"):
            entry = cache.get_quote(sym)
            assert entry is not None, f"{sym} never cached"
            assert entry["symbol"] == sym
            assert entry["quality_status"]  # tagged with a verdict
            assert entry["cached_at"]

        # session cached under the exchange key
        session = cache.get_session("SZSE")
        assert session is not None
        assert "phase" in session

        # latest bar cached (live bar at minimum)
        bar = cache.get_latest_bar("159852")
        assert bar is not None
        assert bar["symbol"] == "159852"
        assert bar["timeframe"] == "1m"

        # quality verdict cached per symbol
        quality = cache.get_quality("159852")
        assert quality is not None
        assert quality["symbol"] == "159852"

        stats = cache.stats()
        assert stats["writes"]["quote"] > 0
        assert stats["writes"]["bar"] > 0
        assert stats["writes"]["session"] >= 1
        assert stats["writes"]["quality"] > 0
        assert stats["write_failures"] == 0
        # mock feed timestamps are monotonic — nothing rejected
        assert stats["stale_updates_rejected"] == 0
