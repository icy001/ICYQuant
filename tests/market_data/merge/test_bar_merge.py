"""Tests for the Historical + Real-time Merge (Commit 008).

Gate coverage (spec §17 analogue):

*   §5 ordering — strictly timestamp ASC.
*   §6 duplicate bars — merge key symbol + exchange + timeframe +
    timestamp dedupes; one bucket appears exactly once.
*   §7 realtime-priority — an unclosed realtime bucket beats history.
*   §8 closed-bar principle — closed/closed conflicts become
    recorded BarRevisions, never silent overwrites.
*   §11 gap honesty — missing trading minutes are reported, not
    fabricated; §12 lunch breaks / closures are not gaps.
*   §9/§10 cold & warm start — history-only then seamless realtime;
    the cache is seeded through Commit 007's timestamp-protected
    set_bar.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from services.market_data.aggregation.bar_service import BarService
from services.market_data.cache import CacheConfig, MarketCache
from services.market_data.domain.bar import Bar
from services.market_data.domain.instrument import Exchange
from services.market_data.merge import (
    HISTORICAL,
    REALTIME,
    BarMergeEngine,
    MergePolicy,
)
from services.market_data.merge.historical_provider import (
    SyntheticHistoricalProvider,
)
from services.market_data.quality.quality_config import QualityConfig

# 2026-09-08 is a Tuesday — a trading day.
# 02:30 UTC == 10:30 CST (CONTINUOUS_AM bar phase)
T = datetime(2026, 9, 8, 2, 30, tzinfo=timezone.utc)
def m(i: int) -> datetime:
    return T + timedelta(minutes=i)


def _bar(symbol: str = "159852", ts=m(0), **kw) -> Bar:
    defaults = dict(
        symbol=symbol,
        exchange=Exchange.SZSE,
        timeframe="1m",
        timestamp=ts,
        open=Decimal("1.230"),
        high=Decimal("1.240"),
        low=Decimal("1.220"),
        close=Decimal("1.235"),
        volume=1000,
        turnover=Decimal("1235.00"),
        is_closed=True,
    )
    defaults.update(kw)
    return Bar(**defaults)


class FakeProvider:
    """Deterministic in-memory history for engine tests.

    Behaves like an authoritative store: it records the engine's
    ``before`` hint (the realtime junction) but does not filter on
    it — overlaps with realtime are exactly what the §7/§8 conflict
    paths exist for.  Returns the *newest* ``limit`` bars.
    """

    name = "fake"

    def __init__(self, bars):
        self._bars = list(bars)
        self.calls: list[dict] = []

    def bars(self, symbol, timeframe="1m", limit=200, *, before=None,
             anchor_price=None):
        self.calls.append(
            {"symbol": symbol, "before": before, "anchor": anchor_price}
        )
        out = [b for b in self._bars if b.symbol == symbol]
        return out[-limit:] if limit else []


class FakeRealtime:
    """BarService stand-in returning a fixed realtime list."""

    def __init__(self, bars):
        self._bars = list(bars)

    def bars(self, symbol, limit=200):
        return [b for b in self._bars if b.symbol == symbol][:limit]


class FakeCache:
    def __init__(self):
        self.written: list[Bar] = []

    def set_bar(self, bar):
        self.written.append(bar)
        return True


def _engine(provider, realtime=None, cache=None, **policy):
    return BarMergeEngine(
        provider,
        bar_service=realtime,
        policy=MergePolicy(enabled=True, **policy),
        market_cache=cache,
    )


# ── §5 ordering ──────────────────────────────────────────────────


class TestOrdering:
    def test_output_is_timestamp_asc(self):
        # history and realtime interleave, realtime handed over in
        # reverse — output must still be strictly ASC
        provider = FakeProvider([_bar(ts=m(0)), _bar(ts=m(2))])
        realtime = FakeRealtime([_bar(ts=m(3)), _bar(ts=m(1))])
        engine = _engine(provider, realtime)
        result = engine.unified("159852")
        bars = [b for b, _ in result["bars"]]
        ts = [b.timestamp for b in bars]
        assert ts == sorted(ts)
        assert ts == [m(0), m(1), m(2), m(3)]

    def test_sources_interleave_correctly(self):
        provider = FakeProvider([_bar(ts=m(0)), _bar(ts=m(2))])
        realtime = FakeRealtime([_bar(ts=m(1)), _bar(ts=m(3))])
        result = _engine(provider, realtime).unified("159852")
        sources = [s for _, s in result["bars"]]
        assert sources == [HISTORICAL, REALTIME, HISTORICAL, REALTIME]

    def test_limit_takes_the_tail(self):
        provider = FakeProvider([_bar(ts=m(i)) for i in range(10)])
        result = _engine(provider, FakeRealtime([])).unified(
            "159852", limit=4
        )
        bars = [b for b, _ in result["bars"]]
        assert [b.timestamp for b in bars] == [m(6), m(7), m(8), m(9)]


# ── §6 duplicate bars ────────────────────────────────────────────


class TestDuplicateBars:
    def test_same_bucket_appears_once(self):
        provider = FakeProvider([_bar(ts=m(0), close=Decimal("1.100"))])
        realtime = FakeRealtime(
            [_bar(ts=m(0), close=Decimal("1.100"), volume=1000)]
        )
        result = _engine(provider, realtime).unified("159852")
        assert len(result["bars"]) == 1
        assert result["counts"]["overlaps"] == 1
        # realtime kept; identical → no revision
        assert result["revisions"] == []

    def test_merge_key_is_symbol_timeframe_timestamp(self):
        provider = FakeProvider([_bar(ts=m(0)), _bar(symbol="513050", ts=m(0))])
        realtime = FakeRealtime([_bar(ts=m(0))])
        result = _engine(provider, realtime).unified("159852")
        assert len(result["bars"]) == 1  # other symbol filtered out


# ── §7 realtime-priority ─────────────────────────────────────────


class TestRealtimePriority:
    def test_open_realtime_bar_wins(self):
        provider = FakeProvider(
            [_bar(ts=m(0), close=Decimal("1.100"), is_closed=True)]
        )
        realtime = FakeRealtime(
            [_bar(ts=m(0), close=Decimal("1.111"), is_closed=False)]
        )
        result = _engine(provider, realtime).unified("159852")
        assert len(result["bars"]) == 1
        bar, source = result["bars"][0]
        assert source == REALTIME
        assert bar.is_closed is False
        assert bar.close == Decimal("1.111")
        # an open bar updating is expected — never a revision
        assert result["revisions"] == []

    def test_closed_realtime_beats_open_history(self):
        provider = FakeProvider([_bar(ts=m(0), is_closed=False)])
        realtime = FakeRealtime([_bar(ts=m(0), is_closed=True)])
        result = _engine(provider, realtime).unified("159852")
        bar, source = result["bars"][0]
        assert source == REALTIME
        assert bar.is_closed is True


# ── §8 closed-bar principle ─────────────────────────────────────


class TestClosedBarRevision:
    def test_conflict_recorded_not_silent(self):
        provider = FakeProvider(
            [_bar(ts=m(0), close=Decimal("1.100"), volume=100)]
        )
        realtime = FakeRealtime(
            [_bar(ts=m(0), close=Decimal("1.234"), volume=200)]
        )
        engine = _engine(provider, realtime)
        result = engine.unified("159852")
        # realtime value kept in the unified series …
        bar, source = result["bars"][0]
        assert source == REALTIME
        assert bar.close == Decimal("1.234")
        # … and the difference is on the audit trail
        assert len(result["revisions"]) == 1
        rev = result["revisions"][0]
        assert rev.symbol == "159852"
        assert rev.timestamp == m(0).isoformat()
        assert rev.fields["close"] == ("1.100", "1.234")
        assert rev.fields["volume"] == (100, 200)
        # engine.revisions() keeps the record for later inspection
        logged = engine.revisions("159852")
        assert len(logged) == 1
        assert logged[0]["fields"]["close"] == {
            "historical": "1.100", "realtime": "1.234",
        }

    def test_identical_closed_bars_no_revision(self):
        provider = FakeProvider([_bar(ts=m(0))])
        realtime = FakeRealtime([_bar(ts=m(0))])
        result = _engine(provider, realtime).unified("159852")
        assert result["revisions"] == []
        assert engine_revisions_empty(result)

    def test_revision_history_capped(self):
        bars_h = [
            _bar(ts=m(i), close=Decimal("1.100")) for i in range(5)
        ]
        bars_r = [
            _bar(ts=m(i), close=Decimal("1.200")) for i in range(5)
        ]
        engine = _engine(
            FakeProvider(bars_h), FakeRealtime(bars_r),
            revision_history=2,
        )
        engine.unified("159852")
        assert len(engine.revisions("159852")) == 2


def engine_revisions_empty(result) -> bool:
    return len(result["revisions"]) == 0


# ── §11 / §12 gaps ───────────────────────────────────────────────


class TestGapHandling:
    def test_missing_minute_is_reported_not_fabricated(self):
        # history jumps 10:30 → 10:32 (CST); 10:31 is missing
        provider = FakeProvider([_bar(ts=m(0)), _bar(ts=m(2))])
        result = _engine(provider).unified("159852")
        assert len(result["bars"]) == 2          # nothing fabricated
        assert result["gaps"] == ["159852_202609080231"]

    def test_lunch_break_is_not_a_gap(self):
        # 03:29 UTC == 11:29 CST, 05:00 UTC == 13:00 CST
        provider = FakeProvider(
            [
                _bar(ts=datetime(2026, 9, 8, 3, 29, tzinfo=timezone.utc)),
                _bar(ts=datetime(2026, 9, 8, 5, 0, tzinfo=timezone.utc)),
            ]
        )
        result = _engine(provider).unified("159852")
        assert result["gaps"] == []

    def test_overnight_is_not_a_gap(self):
        provider = FakeProvider(
            [
                _bar(ts=datetime(2026, 9, 8, 6, 59, tzinfo=timezone.utc)),
                _bar(ts=datetime(2026, 9, 9, 1, 30, tzinfo=timezone.utc)),
            ]
        )
        result = _engine(provider).unified("159852")
        assert result["gaps"] == []

    def test_gap_report_capped(self):
        bars = [_bar(ts=m(0)), _bar(ts=m(60))]
        provider = FakeProvider(bars)
        result = _engine(provider, gap_report_limit=5).unified("159852")
        assert len(result["gaps"]) == 5

    def test_gap_id_convention_matches_aggregator(self):
        provider = FakeProvider([_bar(ts=m(0)), _bar(ts=m(2))])
        result = _engine(provider).unified("159852")
        assert result["gaps"][0].startswith("159852_")


# ── §9 / §10 cold & warm start ──────────────────────────────────


class TestColdWarmStart:
    def test_cold_start_serves_history_only(self):
        provider = FakeProvider(
            [_bar(ts=m(i)) for i in range(3)]
        )
        result = _engine(provider, FakeRealtime([])).unified("159852")
        assert result["counts"]["historical"] == 3
        assert result["counts"]["realtime"] == 0
        assert result["junction"]["mode"] == "COLD"
        assert result["junction"]["seamless"] is False
        assert len(result["bars"]) == 3

    def test_warm_start_joins_seamlessly(self):
        provider = FakeProvider([_bar(ts=m(0)), _bar(ts=m(1))])
        realtime = FakeRealtime(
            [
                _bar(ts=m(2), is_closed=True),
                _bar(ts=m(3), is_closed=False),
            ]
        )
        result = _engine(provider, realtime).unified("159852")
        j = result["junction"]
        assert j["mode"] == "MERGED"
        assert j["seamless"] is True
        assert j["historical_last"] == m(1).isoformat()
        assert j["realtime_first"] == m(2).isoformat()
        assert result["counts"]["overlaps"] == 0
        # 09:30…10:31 | 10:32 10:33 — four bars, one series
        assert len(result["bars"]) == 4

    def test_history_asked_to_stop_before_realtime(self):
        provider = FakeProvider(
            [_bar(ts=m(i)) for i in range(4)]
        )
        realtime = FakeRealtime([_bar(ts=m(2))])
        _engine(provider, realtime).unified("159852")
        # the junction minute belongs to realtime — history must be
        # asked for strictly earlier bars only
        assert provider.calls[0]["before"] == m(2)

    def test_history_anchored_on_realtime_first_open(self):
        provider = FakeProvider([])
        realtime = FakeRealtime(
            [_bar(ts=m(2), open=Decimal("1.234"))]
        )
        _engine(provider, realtime).unified("159852")
        assert provider.calls[0]["anchor"] == Decimal("1.234")

    def test_latest_merged_bar_written_to_cache(self):
        cache = FakeCache()
        provider = FakeProvider([_bar(ts=m(0))])
        realtime = FakeRealtime([_bar(ts=m(1))])
        _engine(provider, realtime, cache=cache).unified("159852")
        assert len(cache.written) == 1
        assert cache.written[0].timestamp == m(1)

    def test_provider_failure_degrades_to_realtime(self):
        class BrokenProvider:
            name = "broken"

            def bars(self, *a, **kw):
                raise RuntimeError("history unavailable")

        realtime = FakeRealtime([_bar(ts=m(0))])
        result = _engine(BrokenProvider(), realtime).unified("159852")
        assert len(result["bars"]) == 1
        assert result["bars"][0][1] == REALTIME

    def test_disabled_policy_is_realtime_passthrough(self):
        provider = FakeProvider([_bar(ts=m(0))])
        realtime = FakeRealtime([_bar(ts=m(1))])
        engine = BarMergeEngine(
            provider,
            bar_service=realtime,
            policy=MergePolicy(enabled=False),
        )
        result = engine.unified("159852")
        assert provider.calls == []          # history never consulted
        assert result["counts"]["historical"] == 0
        assert result["counts"]["realtime"] == 1
        assert result["junction"]["mode"] == "REALTIME_ONLY"


# ── SyntheticHistoricalProvider ──────────────────────────────────


class _FixedClock:
    def __init__(self, now):
        self.now = now

    def __call__(self):
        return self.now


class TestSyntheticProvider:
    def _provider(self, now):
        return SyntheticHistoricalProvider(clock=_FixedClock(now))

    def test_bars_are_closed_and_asc(self):
        # 02:35 UTC == 10:35 CST Tuesday, mid-morning session
        provider = self._provider(datetime(2026, 9, 8, 2, 35, tzinfo=timezone.utc))
        bars = provider.bars("159852", limit=10)
        assert len(bars) == 10
        assert all(b.is_closed for b in bars)
        ts = [b.timestamp for b in bars]
        assert ts == sorted(ts)

    def test_never_touches_current_or_future_minutes(self):
        now = datetime(2026, 9, 8, 2, 35, 30, tzinfo=timezone.utc)
        bars = self._provider(now).bars("159852", limit=100)
        # newest historical minute is 10:34 CST — 10:35 is live
        assert bars[-1].timestamp == datetime(
            2026, 9, 8, 2, 34, tzinfo=timezone.utc
        )

    def test_respects_before_boundary(self):
        provider = self._provider(
            datetime(2026, 9, 8, 2, 35, tzinfo=timezone.utc)
        )
        before = datetime(2026, 9, 8, 2, 30, tzinfo=timezone.utc)
        bars = provider.bars("159852", limit=50, before=before)
        assert bars
        assert all(b.timestamp < before for b in bars)
        # newest is the minute just before the realtime junction
        assert bars[-1].timestamp == datetime(
            2026, 9, 8, 2, 29, tzinfo=timezone.utc
        )

    def test_no_lunch_break_minutes(self):
        # walk from 13:05 CST (05:05 UTC) back through lunch
        provider = self._provider(
            datetime(2026, 9, 8, 5, 5, tzinfo=timezone.utc)
        )
        bars = provider.bars("159852", limit=120)
        cst = [b.timestamp.astimezone(
            timezone(timedelta(hours=8))
        ) for b in bars]
        for local in cst:
            t = local.time()
            assert not (datetime.strptime("11:30", "%H:%M").time() <= t
                        < datetime.strptime("13:00", "%H:%M").time())

    def test_no_minutes_outside_bar_phases(self):
        provider = self._provider(
            datetime(2026, 9, 8, 2, 35, tzinfo=timezone.utc)
        )
        bars = provider.bars("159852", limit=300)
        CSTZ = timezone(timedelta(hours=8))
        for b in bars:
            local = b.timestamp.astimezone(CSTZ)
            t = local.time()
            am = datetime.strptime("09:30", "%H:%M").time() <= t < \
                datetime.strptime("11:30", "%H:%M").time()
            pm = datetime.strptime("13:00", "%H:%M").time() <= t < \
                datetime.strptime("15:00", "%H:%M").time()
            assert am or pm

    def test_walks_back_across_days(self):
        # 09:35 CST Tuesday with a big limit → must reach Monday
        provider = self._provider(
            datetime(2026, 9, 8, 1, 35, tzinfo=timezone.utc)
        )
        bars = provider.bars("159852", limit=100)
        days = {
            b.timestamp.astimezone(
                timezone(timedelta(hours=8))
            ).date() for b in bars
        }
        assert datetime(2026, 9, 7).date() in days   # Monday
        assert len(bars) == 100

    def test_skips_weekend(self):
        # Sunday 2026-09-06 12:00 CST — history must land on Friday
        provider = self._provider(
            datetime(2026, 9, 6, 4, 0, tzinfo=timezone.utc)
        )
        bars = provider.bars("159852", limit=10)
        CSTZ = timezone(timedelta(hours=8))
        days = {b.timestamp.astimezone(CSTZ).date() for b in bars}
        assert days == {datetime(2026, 9, 4).date()}  # Friday

    def test_deterministic(self):
        now = datetime(2026, 9, 8, 2, 35, tzinfo=timezone.utc)
        p1 = self._provider(now)
        p2 = self._provider(now)
        b1 = p1.bars("159852", limit=50)
        b2 = p2.bars("159852", limit=50)
        assert [b.as_dict() for b in b1] == [b.as_dict() for b in b2]

    def test_window_shift_is_stable(self):
        """Same anchor, shifted window → overlapping minutes get the
        same values (per-minute determinism)."""
        now = datetime(2026, 9, 8, 2, 35, tzinfo=timezone.utc)
        provider = self._provider(now)
        wide = provider.bars("159852", limit=60, anchor_price=Decimal("1.234"))
        narrow = provider.bars("159852", limit=30, anchor_price=Decimal("1.234"))
        wide_tail = {b.timestamp: b.as_dict() for b in wide[-30:]}
        for b in narrow:
            assert wide_tail[b.timestamp] == b.as_dict()

    def test_anchor_makes_seamless_junction(self):
        provider = self._provider(
            datetime(2026, 9, 8, 2, 35, tzinfo=timezone.utc)
        )
        bars = provider.bars(
            "159852", limit=5, anchor_price=Decimal("1.234")
        )
        # newest historical close == realtime's first open → seamless
        assert bars[-1].close == Decimal("1.234")

    def test_ohlc_is_valid(self):
        from services.market_data.quality.bar_quality import validate_bar

        provider = self._provider(
            datetime(2026, 9, 8, 2, 35, tzinfo=timezone.utc)
        )
        for b in provider.bars("159852", limit=100):
            assert validate_bar(b).valid, b.as_dict()


# ── §17 time continuity ─────────────────────────────────────────


class TestTimeContinuity:
    """§17 — within a continuous trading range Δt = 1 minute; the
    11:29 → 13:00 lunch jump is a normal junction, not a gap."""

    def _provider(self, now):
        return SyntheticHistoricalProvider(clock=_FixedClock(now))

    def test_one_minute_steps_within_session(self):
        provider = self._provider(
            datetime(2026, 9, 8, 2, 35, tzinfo=timezone.utc)
        )
        bars = provider.bars("159852", limit=30)
        for prev, cur in zip(bars, bars[1:]):
            assert cur.timestamp - prev.timestamp == timedelta(minutes=1)

    def test_lunch_junction_is_91_minutes(self):
        # 13:05 CST; limit 125 = PM 13:00–13:04 (5) + AM
        # 09:30–11:29 (120) — exactly one seam
        provider = self._provider(
            datetime(2026, 9, 8, 5, 5, tzinfo=timezone.utc)
        )
        bars = provider.bars("159852", limit=125)
        assert len(bars) == 125
        diffs = [
            cur.timestamp - prev.timestamp
            for prev, cur in zip(bars, bars[1:])
        ]
        jumps = [d for d in diffs if d != timedelta(minutes=1)]
        assert len(jumps) == 1                     # exactly one seam
        assert jumps[0] == timedelta(minutes=91)   # 11:29 → 13:00

    def test_day_boundary_is_overnight_jump(self):
        # Tuesday 09:35 CST; limit 245 = Tue 09:30–09:34 (5) +
        # Monday's full session (240) — exactly two seams
        provider = self._provider(
            datetime(2026, 9, 8, 1, 35, tzinfo=timezone.utc)
        )
        bars = provider.bars("159852", limit=245)
        assert len(bars) == 245
        diffs = [
            cur.timestamp - prev.timestamp
            for prev, cur in zip(bars, bars[1:])
        ]
        jumps = [d for d in diffs if d != timedelta(minutes=1)]
        # exactly one overnight seam (Monday 14:59 → Tuesday 09:30
        # = 1111 minutes) and one lunch seam (91 minutes)
        assert sorted(jumps) == [
            timedelta(minutes=91), timedelta(minutes=1111)
        ]

    def test_merged_series_junction_is_adjacent(self):
        """§1 — history's last bucket and realtime's first bucket
        are consecutive minutes of the same session."""
        provider = FakeProvider(
            [_bar(ts=m(i)) for i in range(3)]
        )
        realtime = FakeRealtime([_bar(ts=m(3), is_closed=False)])
        result = _engine(provider, realtime).unified("159852")
        bars = [b for b, _ in result["bars"]]
        assert len(bars) == 4
        for prev, cur in zip(bars, bars[1:]):
            assert cur.timestamp - prev.timestamp == timedelta(minutes=1)


# ── §13 Redis integration (real MarketCache) ─────────────────────


class TestRedisIntegration:
    """§19 Redis gate — historical/realtime/merged state → Redis,
    old-bar protection, cache restart recovery."""

    def _real_cache(self) -> MarketCache:
        return MarketCache(
            config=CacheConfig(enabled=True),
            quality_config=QualityConfig(),
        )

    def test_historical_to_redis_cold_start(self):
        """Cold start (§9): no realtime yet — the newest merged
        historical bar already lands in the cache."""
        cache = self._real_cache()
        provider = FakeProvider(
            [_bar(ts=m(i), close=Decimal(f"1.2{i}")) for i in range(3)]
        )
        _engine(provider, FakeRealtime([]), cache=cache).unified("159852")
        cached = cache.get_latest_bar("159852")
        assert cached is not None
        assert cached["timestamp"] == m(2).isoformat()
        assert cached["close"] == "1.22"

    def test_old_bar_protection(self):
        """Old bar protection — a merge whose latest bar is OLDER
        than what the cache already holds must never regress it."""
        cache = self._real_cache()
        provider = FakeProvider([_bar(ts=m(0))])
        realtime = FakeRealtime(
            [_bar(ts=m(2), close=Decimal("1.234"))]
        )
        engine = _engine(provider, realtime, cache=cache)
        engine.unified("159852")
        assert cache.get_latest_bar("159852")["timestamp"] == m(2).isoformat()

        # a later merge sees only stale/older realtime data (e.g. a
        # lagging replica) — the cache must keep the newer state
        engine._realtime = FakeRealtime([_bar(ts=m(1))])
        engine.unified("159852")
        assert cache.get_latest_bar("159852")["timestamp"] == m(2).isoformat()
        assert cache.get_latest_bar("159852")["close"] == "1.234"

    def test_cache_restart_recovery(self):
        """§10 warm start — Redis restarts, the cache is empty, but
        the series never restarts from zero: the next merge rebuilds
        the same unified state and re-seeds the cache."""
        provider = FakeProvider(
            [_bar(ts=m(i)) for i in range(3)]
        )
        realtime = FakeRealtime(
            [_bar(ts=m(3), is_closed=False)]
        )

        cache_a = self._real_cache()
        engine_a = _engine(provider, realtime, cache=cache_a)
        first = engine_a.unified("159852")
        ts_a = [b.timestamp for b, _ in first["bars"]]
        assert cache_a.get_latest_bar("159852") is not None

        # ── Redis restart: brand-new empty cache ──
        cache_b = self._real_cache()
        assert cache_b.get_latest_bar("159852") is None

        engine_b = _engine(provider, realtime, cache=cache_b)
        second = engine_b.unified("159852")
        ts_b = [b.timestamp for b, _ in second["bars"]]

        # the series is identical — not "from zero"
        assert ts_b == ts_a
        assert second["counts"] == first["counts"]
        assert second["junction"]["seamless"] is True
        # and the restarted cache is re-seeded with the latest bar
        reseeded = cache_b.get_latest_bar("159852")
        assert reseeded is not None
        assert reseeded["timestamp"] == m(3).isoformat()


# ── E2E: engine + synthetic provider + real BarService + cache ──


class TestMergeEndToEnd:
    def test_realtime_feed_plus_history(self):
        from services.market_data.adapters.mock import MockMarketDataAdapter
        from services.market_data.quote_service import (
            QuoteFeed, QuoteService,
        )
        from services.market_data.validators.market_data_validator import (
            MarketDataValidator,
        )

        import time as _time

        svc = QuoteService(validator=MarketDataValidator(stale_seconds=600))
        bars = BarService()
        cache = MarketCache(
            config=CacheConfig(enabled=True),
            quality_config=QualityConfig(),
        )
        engine = BarMergeEngine(
            SyntheticHistoricalProvider(),
            bar_service=bars,
            policy=MergePolicy(enabled=True),
            market_cache=cache,
        )
        feed = QuoteFeed(
            MockMarketDataAdapter(seed=8), svc, interval=0.01,
            bar_service=bars, market_cache=cache,
        )
        feed.start(symbols=["159852"])
        deadline = _time.time() + 8.0
        while _time.time() < deadline:
            if len(bars.bars("159852", 50)) >= 1:
                break
            _time.sleep(0.05)
        result = engine.unified("159852", limit=60)
        feed.stop()

        assert result["counts"]["realtime"] >= 1
        assert result["counts"]["historical"] >= 1
        assert result["junction"]["mode"] == "MERGED"
        # no conflicting buckets — the seam is seamless
        assert result["counts"]["overlaps"] == 0
        assert result["junction"]["seamless"] is True
        # strictly ASC, no duplicate bucket
        ts = [b.timestamp for b, _ in result["bars"]]
        assert ts == sorted(ts)
        assert len(ts) == len(set(ts))
        # merged latest bar flowed into the cache (§13)
        latest = cache.get_latest_bar("159852")
        assert latest is not None
        assert latest["symbol"] == "159852"
