"""Tests for the Market Data Quality Gate (Commit 006).

Gate coverage:
    Freshness detection (FRESH / WARNING / STALE boundaries)
    Duplicate detection (quote identity)
    Timestamp validation (future / regression / cross-day jump)
    Price validation (negative, crossed book)
    Price outlier (marked, never modified)
    Volume validation (negative, intra-day regression, day reset)
    Trading session validation (lunch break → recorded, not tradable)
    Quality result shape + tradable semantics + actions
    Quarantine (never deleted, traceable)
    QuoteService integration (PASS / REJECT flow)
    Bar quality (OHLCV consistency)
    Env-driven configuration
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

import pytest

from services.market_data.calendar.trading_calendar import CST
from services.market_data.domain.bar import Bar
from services.market_data.domain.instrument import Exchange
from services.market_data.domain.quote import MarketQuote
from services.market_data.exceptions.market_data_error import (
    QualityRejectedError,
)
from services.market_data.quality import (
    QualityConfig,
    QualityGate,
    QualityStatus,
    validate_bar,
)
from services.market_data.quality.quarantine import QuarantineStore
from services.market_data.quote_service import QuoteService

import datetime as _dt


def cst(y, m, d, h=0, mi=0, s=0, us=0):
    return _dt.datetime(y, m, d, h, mi, s, us, tzinfo=CST)


# 2026-09-08 is a Tuesday — normal trading day, 10:00 = continuous AM.
NOW = cst(2026, 9, 8, 10, 0, 0)


def q(
    ts=None,
    last="1.000",
    bid=None,
    ask=None,
    volume=0,
    symbol="159852",
    turnover="0",
) -> MarketQuote:
    last = Decimal(last)
    bid = Decimal(bid) if bid is not None else last
    ask = Decimal(ask) if ask is not None else last
    return MarketQuote(
        symbol=symbol,
        exchange=Exchange.SZSE,
        timestamp=ts or NOW,
        last=last,
        bid=bid,
        ask=ask,
        bid_size=10000,
        ask_size=10000,
        volume=volume,
        turnover=Decimal(turnover),
    )


# --- Freshness ---------------------------------------------------------------


class TestFreshness:
    def test_fresh_within_threshold(self):
        gate = QualityGate()
        quote = q(ts=NOW - timedelta(milliseconds=100))
        result = gate.evaluate(quote, now=NOW)
        assert result.status is QualityStatus.FRESH
        assert result.quote_age_ms == 100
        assert result.tradable is True
        assert result.passed is True

    def test_warning_between_fresh_and_stale(self):
        gate = QualityGate()
        quote = q(ts=NOW - timedelta(milliseconds=5000))
        result = gate.evaluate(quote, now=NOW)
        assert result.status is QualityStatus.WARNING
        # default config: WARNING produces no new orders
        assert result.tradable is False
        assert result.passed is True  # still valid data

    def test_stale_beyond_stale_line(self):
        gate = QualityGate()
        quote = q(ts=NOW - timedelta(milliseconds=12483))
        result = gate.evaluate(quote, now=NOW)
        assert result.status is QualityStatus.STALE
        assert result.quote_age_ms == 12483
        assert result.tradable is False
        assert result.action == "BLOCK_TRADING"
        assert result.passed is True  # valid data, merely old

    def test_latency_reported(self):
        gate = QualityGate()
        received = NOW + timedelta(milliseconds=53)
        quote = q(ts=NOW - timedelta(milliseconds=0))
        quote = MarketQuote(
            symbol="159852", exchange=Exchange.SZSE, timestamp=quote.timestamp,
            last=quote.last, bid=quote.bid, ask=quote.ask,
            bid_size=10000, ask_size=10000,
            received_timestamp=received,
        )
        result = gate.evaluate(quote, now=NOW)
        assert result.latency_ms == 53
        assert result.status is QualityStatus.FRESH

    def test_warning_trading_allowed_when_configured(self):
        gate = QualityGate(
            config=QualityConfig(allow_warning_trading=True)
        )
        quote = q(ts=NOW - timedelta(milliseconds=5000))
        result = gate.evaluate(quote, now=NOW)
        assert result.status is QualityStatus.WARNING
        assert result.tradable is True


# --- Duplicate detection --------------------------------------------------------


class TestDuplicate:
    def test_exact_resend_is_duplicate(self):
        gate = QualityGate()
        first = gate.evaluate(q(), now=NOW)
        assert first.status is QualityStatus.FRESH
        second = gate.evaluate(q(), now=NOW)
        assert second.status is QualityStatus.INVALID
        assert "DUPLICATE" in second.reasons
        assert second.passed is False
        assert second.action == "DROP"

    def test_sequence_id_distinguishes_same_timestamp(self):
        gate = QualityGate()
        r1 = gate.evaluate(q(), sequence_id="1", now=NOW)
        r2 = gate.evaluate(q(), sequence_id="2", now=NOW)
        assert "DUPLICATE" not in r2.reasons
        assert r2.status is QualityStatus.FRESH

    def test_different_timestamp_not_duplicate(self):
        gate = QualityGate()
        gate.evaluate(q(ts=NOW), now=NOW)
        r2 = gate.evaluate(
            q(ts=NOW + timedelta(seconds=1)), now=NOW + timedelta(seconds=1)
        )
        assert "DUPLICATE" not in r2.reasons

    def test_duplicate_recorded_not_deleted(self):
        gate = QualityGate()
        gate.evaluate(q(), now=NOW)
        gate.evaluate(q(), now=NOW)
        items = gate.quarantine.recent(10)
        assert len(items) == 1
        assert "DUPLICATE" in items[0]["reasons"]
        # payload preserved
        assert items[0]["quote"]["symbol"] == "159852"
        assert items[0]["status"] == "INVALID"


# --- Timestamp validation --------------------------------------------------------


class TestTimestampValidation:
    def test_future_timestamp_rejected(self):
        gate = QualityGate()
        quote = q(ts=NOW + timedelta(seconds=10))
        result = gate.evaluate(quote, now=NOW)
        assert result.status is QualityStatus.INVALID
        assert "FUTURE_TIMESTAMP" in result.reasons
        assert result.checks["timestamp"] is False

    def test_small_clock_drift_tolerated(self):
        gate = QualityGate()
        quote = q(ts=NOW + timedelta(seconds=3))  # < 5s tolerance
        result = gate.evaluate(quote, now=NOW)
        assert "FUTURE_TIMESTAMP" not in result.reasons

    def test_timestamp_regression(self):
        gate = QualityGate()
        gate.evaluate(q(ts=NOW), now=NOW)
        older = gate.evaluate(
            q(ts=NOW - timedelta(seconds=1)), now=NOW
        )
        assert older.status is QualityStatus.INVALID
        assert "TIMESTAMP_REGRESSION" in older.reasons

    def test_cross_day_jump_detected(self):
        """09-08 → 09-10 skips the whole trading day 09-09."""
        gate = QualityGate()
        day1 = cst(2026, 9, 8, 10, 0)
        gate.evaluate(q(ts=day1), now=day1)
        # quote claims 09-10 (two trading days ahead of 09-08)
        day3 = cst(2026, 9, 10, 10, 0)
        jumped = gate.evaluate(q(ts=day3), now=day3)
        assert jumped.status is QualityStatus.INVALID
        assert "CROSS_DAY_JUMP" in jumped.reasons

    def test_normal_next_trading_day_is_not_a_jump(self):
        """09-08 → 09-09 is a normal session rollover."""
        gate = QualityGate()
        day1 = cst(2026, 9, 8, 14, 59)
        gate.evaluate(q(ts=day1), now=day1)
        day2 = cst(2026, 9, 9, 9, 31)
        result = gate.evaluate(q(ts=day2), now=day2)
        assert "CROSS_DAY_JUMP" not in result.reasons
        assert result.status is QualityStatus.FRESH

    def test_holiday_block_is_not_a_jump(self):
        """09-30 → 10-08 crosses National Day; the calendar knows."""
        gate = QualityGate()
        before = cst(2026, 9, 30, 14, 59)
        gate.evaluate(q(ts=before), now=before)
        after = cst(2026, 10, 8, 9, 31)
        result = gate.evaluate(q(ts=after), now=after)
        assert "CROSS_DAY_JUMP" not in result.reasons


# --- Price validation -------------------------------------------------------------


class TestPriceValidation:
    def test_negative_last_invalid(self):
        gate = QualityGate()
        result = gate.evaluate(q(last="-1.000"), now=NOW)
        assert result.status is QualityStatus.INVALID
        assert "INVALID_PRICE" in result.reasons
        assert result.checks["price"] is False

    def test_crossed_book_invalid(self):
        """bid 1.235 > ask 1.233 → INVALID."""
        gate = QualityGate()
        result = gate.evaluate(q(bid="1.235", ask="1.233"), now=NOW)
        assert result.status is QualityStatus.INVALID
        assert "CROSSED_BOOK" in result.reasons
        assert result.checks["bid_ask"] is False

    def test_normal_prices_pass(self):
        gate = QualityGate()
        result = gate.evaluate(q(bid="0.999", ask="1.001"), now=NOW)
        assert result.checks["price"] is True
        assert result.checks["bid_ask"] is True
        assert result.status is QualityStatus.FRESH


# --- Price outlier ------------------------------------------------------------------


class TestPriceOutlier:
    def test_large_deviation_quarantined(self):
        """1.200 → 9.999 must not silently feed the strategy."""
        gate = QualityGate()
        gate.evaluate(q(last="1.200", ts=NOW), now=NOW)
        later = NOW + timedelta(seconds=1)
        result = gate.evaluate(
            q(last="9.999", ts=later), now=later
        )
        assert result.status is QualityStatus.QUARANTINED
        assert "PRICE_OUTLIER" in result.reasons
        assert result.tradable is False
        assert result.action == "QUARANTINE"
        assert result.passed is False

    def test_outlier_marks_never_modifies_price(self):
        gate = QualityGate()
        gate.evaluate(q(last="1.200", ts=NOW), now=NOW)
        later = NOW + timedelta(seconds=1)
        quote = q(last="9.999", ts=later)
        gate.evaluate(quote, now=later)
        # the raw price is untouched — marked, not mutated
        assert quote.last == Decimal("9.999")

    def test_small_move_not_outlier(self):
        gate = QualityGate()
        gate.evaluate(q(last="1.200", ts=NOW), now=NOW)
        later = NOW + timedelta(seconds=1)
        result = gate.evaluate(q(last="1.260", ts=later), now=later)
        assert "PRICE_OUTLIER" not in result.reasons
        assert result.status is QualityStatus.FRESH

    def test_real_limit_up_survives_as_quarantine_not_invalid(self):
        """A ±10% limit move is a *real* market event — it is
        QUARANTINED for review, never INVALID."""
        gate = QualityGate(
            config=QualityConfig(outlier_pct=Decimal("5"))
        )
        gate.evaluate(q(last="1.000", ts=NOW), now=NOW)
        later = NOW + timedelta(seconds=1)
        result = gate.evaluate(q(last="1.100", ts=later), now=later)
        assert result.status is QualityStatus.QUARANTINED
        assert "PRICE_OUTLIER" in result.reasons


# --- Volume validation ----------------------------------------------------------------


class TestVolumeValidation:
    def test_negative_volume_invalid(self):
        gate = QualityGate()
        result = gate.evaluate(q(volume=-5), now=NOW)
        assert result.status is QualityStatus.INVALID
        assert "INVALID_VOLUME" in result.reasons

    def test_negative_turnover_invalid(self):
        gate = QualityGate()
        result = gate.evaluate(q(turnover="-1"), now=NOW)
        assert result.status is QualityStatus.INVALID
        assert "INVALID_VOLUME" in result.reasons

    def test_intra_day_volume_regression(self):
        """2,000,000 → 1,500,000 on the SAME day is an anomaly."""
        gate = QualityGate()
        t1 = cst(2026, 9, 8, 10, 31)
        gate.evaluate(q(ts=t1, volume=2_000_000), now=t1)
        t2 = cst(2026, 9, 8, 10, 32)
        result = gate.evaluate(q(ts=t2, volume=1_500_000), now=t2)
        assert result.status is QualityStatus.INVALID
        assert "VOLUME_REGRESSION" in result.reasons

    def test_cross_day_volume_reset_is_normal(self):
        """New trading day → cumulative volume restarts from zero."""
        gate = QualityGate()
        day1 = cst(2026, 9, 8, 14, 59)
        gate.evaluate(q(ts=day1, volume=10_000), now=day1)
        day2 = cst(2026, 9, 9, 9, 31)
        result = gate.evaluate(q(ts=day2, volume=500), now=day2)
        assert "VOLUME_REGRESSION" not in result.reasons
        assert result.status is QualityStatus.FRESH

    def test_volume_monotonic_increase_ok(self):
        gate = QualityGate()
        t1 = cst(2026, 9, 8, 10, 31)
        gate.evaluate(q(ts=t1, volume=100), now=t1)
        t2 = cst(2026, 9, 8, 10, 32)
        result = gate.evaluate(q(ts=t2, volume=200), now=t2)
        assert result.checks["volume"] is True
        assert result.status is QualityStatus.FRESH


# --- Trading session validation -----------------------------------------------------


class TestSessionValidation:
    def test_lunch_break_quote_recorded_not_tradable(self):
        """12:15 quote: legal data, wrong phase — recorded with
        SESSION_INACTIVE, never silently dropped."""
        lunch = cst(2026, 9, 8, 12, 15)
        gate = QualityGate()
        result = gate.evaluate(q(ts=lunch), now=lunch)
        assert "SESSION_INACTIVE" in result.reasons
        assert result.checks["session"] is False
        assert result.status is QualityStatus.WARNING
        assert result.tradable is False
        # recorded — the data itself is fine
        assert result.passed is True

    def test_auction_quote_not_tradable(self):
        t = cst(2026, 9, 8, 9, 22)
        gate = QualityGate()
        result = gate.evaluate(q(ts=t), now=t)
        assert "SESSION_INACTIVE" in result.reasons
        assert result.tradable is False

    def test_non_trading_day_quote(self):
        t = cst(2026, 9, 6, 10, 0)  # Sunday
        gate = QualityGate()
        result = gate.evaluate(q(ts=t), now=t)
        assert "SESSION_INACTIVE" in result.reasons
        assert result.tradable is False

    def test_continuous_session_tradable(self):
        t = cst(2026, 9, 8, 13, 5)  # PM continuous
        gate = QualityGate()
        result = gate.evaluate(q(ts=t), now=t)
        assert result.checks["session"] is True
        assert result.status is QualityStatus.FRESH
        assert result.tradable is True


# --- Quality result shape -----------------------------------------------------------


class TestQualityResult:
    def test_all_checks_present(self):
        gate = QualityGate()
        result = gate.evaluate(q(), now=NOW)
        for check in (
            "symbol", "exchange", "timestamp", "freshness",
            "price", "bid_ask", "volume", "session",
            "duplicate", "regression", "outlier",
        ):
            assert check in result.checks, f"missing check {check}"
            assert result.checks[check] is True

    def test_as_dict_shape(self):
        gate = QualityGate()
        d = gate.evaluate(q(), now=NOW).as_dict()
        for key in (
            "symbol", "status", "passed", "tradable", "action",
            "checks", "reasons", "quote_age_ms", "latency_ms",
            "checked_at",
        ):
            assert key in d, f"missing {key}"
        assert d["status"] == "FRESH"
        assert d["tradable"] is True

    def test_action_mapping(self):
        gate = QualityGate()
        assert gate.evaluate(q(), now=NOW).action == "PASS"

        stale_q = q(ts=NOW - timedelta(seconds=12))
        assert gate.evaluate(stale_q, now=NOW).action == "BLOCK_TRADING"

    def test_invalid_symbol(self):
        gate = QualityGate()
        bad = q(symbol="abc")
        result = gate.evaluate(bad, now=NOW)
        assert result.status is QualityStatus.INVALID
        assert "INVALID_SYMBOL" in result.reasons

    def test_bad_exchange(self):
        gate = QualityGate()
        quote = q()
        bad = MarketQuote(
            symbol=quote.symbol, exchange="SZSE",  # not an Exchange
            timestamp=quote.timestamp, last=quote.last,
            bid=quote.bid, ask=quote.ask,
        )
        result = gate.evaluate(bad, now=NOW)
        assert result.status is QualityStatus.INVALID
        assert "INVALID_EXCHANGE" in result.reasons

    def test_stats_accumulate(self):
        gate = QualityGate()
        gate.evaluate(q(ts=NOW), now=NOW)                 # FRESH pass
        gate.evaluate(q(ts=NOW), now=NOW)                  # duplicate
        gate.evaluate(q(last="-1"), now=NOW + timedelta(seconds=1))
        stats = gate.stats()
        assert stats["evaluated"] == 3
        assert stats["rejected"] == 2
        assert stats["by_status"]["INVALID"] == 2
        assert stats["by_status"]["FRESH"] == 1


# --- Quarantine ----------------------------------------------------------------------


class TestQuarantine:
    def test_rejected_data_preserved_with_context(self):
        gate = QualityGate()
        stale_q = q(ts=NOW - timedelta(seconds=12))
        gate.evaluate(stale_q, now=NOW)
        # STALE passes (valid data) — not quarantined
        assert gate.quarantine.count() == 0

        gate.evaluate(q(last="-1"), now=NOW)
        items = gate.quarantine.recent()
        assert len(items) == 1
        item = items[0]
        assert item["symbol"] == "159852"
        assert item["status"] == "INVALID"
        assert item["reasons"] == ["INVALID_PRICE"]
        assert item["quote"]["last"] == "-1"

    def test_quarantine_traceability_chain(self):
        """Quote → Quality Gate → reason → order blocked."""
        gate = QualityGate()
        gate.evaluate(q(last="-1"), now=NOW)
        item = gate.quarantine.recent()[0]
        assert item["action"] == "BLOCK_TRADING"
        assert item["received_at"] is not None

    def test_quarantine_stats_by_reason(self):
        gate = QualityGate()
        t1 = cst(2026, 9, 8, 10, 0)
        gate.evaluate(q(ts=t1), now=t1)          # baseline — pass
        gate.evaluate(q(ts=t1), now=t1)          # duplicate — reject
        t2 = t1 + timedelta(seconds=1)
        gate.evaluate(q(ts=t2, last="-1"), now=t2)  # bad price — reject
        stats = gate.quarantine.stats()
        assert stats["total_rejected"] == 2
        assert stats["by_reason"]["DUPLICATE"] == 1
        assert stats["by_reason"]["INVALID_PRICE"] == 1

    def test_bounded_capacity(self):
        store = QuarantineStore(capacity=3)
        for i in range(5):
            store.record(
                q(last="-1", ts=NOW + timedelta(seconds=i)),
                _mk_result(i),
            )
        assert store.count() == 3
        assert store.stats()["total_rejected"] == 5


def _mk_result(i: int):
    from services.market_data.quality.quality_result import (
        MarketDataQualityResult,
    )

    return MarketDataQualityResult(
        symbol="159852",
        status=QualityStatus.INVALID,
        reasons=["INVALID_PRICE"],
        quote_age_ms=i,
        latency_ms=0,
        checked_at=NOW,
    )


# --- QuoteService integration ---------------------------------------------------------


class TestQuoteServiceIntegration:
    def _service(self, gate=None):
        # validator with a wide staleness window: the quality gate
        # (not the legacy validator) is under test here, and fixed
        # historical timestamps are used for session determinism.
        from services.market_data.validators.market_data_validator import (
            MarketDataValidator,
        )

        return QuoteService(
            quality_gate=gate if gate is not None else QualityGate(),
            validator=MarketDataValidator(stale_seconds=10**9),
        )

    def test_valid_quote_passes_and_stores(self):
        svc = self._service()
        quote = q(ts=_dt.datetime.now(_dt.timezone.utc))
        stored = svc.update(quote)
        assert stored is not None
        assert svc.latest("159852") is not None

    def test_invalid_quote_rejected_not_stored(self):
        svc = self._service()
        with pytest.raises(QualityRejectedError):
            svc.update(q(bid="1.235", ask="1.233"))
        assert svc.latest("159852") is None

    def test_duplicate_rejected_on_resend(self):
        svc = self._service()
        quote = q(ts=NOW)
        svc.update(quote)
        with pytest.raises(QualityRejectedError):
            svc.update(quote)
        assert svc.stats()["quality_rejected"] == 1

    def test_rejected_quote_goes_to_quarantine(self):
        svc = self._service()
        with pytest.raises(QualityRejectedError):
            svc.update(q(last="-1"))
        gate = svc.quality_gate
        assert gate.quarantine.count() == 1

    def test_view_carries_quality(self):
        svc = QuoteService()  # no gate → derive mode
        quote = q(ts=_dt.datetime.now(_dt.timezone.utc))
        svc.update(quote)
        view = svc.snapshot(["159852"])[0]
        assert "quality" in view
        quality = view["quality"]
        assert quality["checks"]["price"] is True
        assert quality["checks"]["bid_ask"] is True
        assert "status" in quality
        assert "reasons" in quality

    def test_view_uses_gate_verdict_when_attached(self):
        gate = QualityGate()
        svc = self._service(gate)
        # 10:31 AM session quote (continuous trading)
        t = cst(2026, 9, 8, 10, 31)
        svc.update(q(ts=t))
        view = svc.snapshot(["159852"])[0]
        quality = view["quality"]
        # gate verdict carries the stateful checks (derive does not)
        assert "duplicate" in quality["checks"]
        assert "outlier" in quality["checks"]
        assert "regression" in quality["checks"]
        # 10:31 AM is continuous trading
        assert quality["checks"]["session"] is True

    def test_stats_report_gate_state(self):
        svc = QuoteService()
        assert svc.stats()["quality_gate_enabled"] is False
        svc2 = self._service()
        assert svc2.stats()["quality_gate_enabled"] is True


# --- Bar quality ------------------------------------------------------------------------


class TestBarQuality:
    def _bar(self, o="1.230", h="1.240", l="1.220", c="1.235", v=100):
        return Bar(
            symbol="159852",
            exchange=Exchange.SZSE,
            timeframe="1m",
            timestamp=NOW,
            open=Decimal(o), high=Decimal(h), low=Decimal(l),
            close=Decimal(c), volume=v,
        )

    def test_valid_bar(self):
        quality = validate_bar(self._bar())
        assert quality.valid is True
        assert quality.reasons == []

    def test_low_above_high(self):
        quality = validate_bar(self._bar(l="1.250", h="1.240"))
        assert quality.valid is False
        assert "HIGH_LT_LOW" in quality.reasons

    def test_high_below_max_open_close(self):
        """O=1.230 C=1.235 H must be >= 1.235."""
        quality = validate_bar(self._bar(h="1.232"))
        assert quality.valid is False
        assert "HIGH_LT_MAX_OC" in quality.reasons

    def test_low_above_min_open_close(self):
        """O=1.230 C=1.235 L must be <= 1.230."""
        quality = validate_bar(self._bar(l="1.231"))
        assert quality.valid is False
        assert "LOW_GT_MIN_OC" in quality.reasons

    def test_negative_volume(self):
        quality = validate_bar(self._bar(v=-1))
        assert quality.valid is False
        assert "NEGATIVE_VOLUME" in quality.reasons

    def test_bar_snapshot_exposes_quality(self):
        from services.market_data.aggregation.bar_service import BarService

        svc = BarService()
        svc.on_quote(q(ts=NOW, volume=100))
        snapshot = svc.as_snapshot("159852")
        assert "quality" in snapshot
        assert snapshot["quality"]["checked"] >= 1
        assert snapshot["quality"]["invalid_count"] == 0
        assert snapshot["quality"]["invalid_bars"] == []


# --- Configuration ------------------------------------------------------------------------


class TestQualityConfig:
    def test_defaults(self):
        cfg = QualityConfig()
        assert cfg.fresh_ms == 3000
        assert cfg.stale_ms == 10000
        assert cfg.outlier_pct == Decimal("30")
        assert cfg.allow_warning_trading is False

    def test_env_overrides(self, monkeypatch):
        monkeypatch.setenv("MARKET_DATA_FRESH_MS", "500")
        monkeypatch.setenv("MARKET_DATA_WARNING_MS", "2000")
        monkeypatch.setenv("MARKET_DATA_STALE_MS", "4000")
        monkeypatch.setenv("MARKET_DATA_OUTLIER_PCT", "5")
        monkeypatch.setenv("MARKET_DATA_ALLOW_WARNING_TRADING", "true")
        cfg = QualityConfig.from_env()
        assert cfg.fresh_ms == 500
        assert cfg.warning_ms == 2000
        assert cfg.stale_ms == 4000
        assert cfg.outlier_pct == Decimal("5")
        assert cfg.allow_warning_trading is True

    def test_env_thresholds_drive_gate(self, monkeypatch):
        monkeypatch.setenv("MARKET_DATA_FRESH_MS", "500")
        monkeypatch.setenv("MARKET_DATA_STALE_MS", "1000")
        gate = QualityGate(config=QualityConfig.from_env())
        # 800ms age: FRESH line is 500, stale line 1000 → WARNING
        result = gate.evaluate(
            q(ts=NOW - timedelta(milliseconds=800)), now=NOW
        )
        assert result.status is QualityStatus.WARNING
        # 2000ms age → STALE (ts moves forward: no regression)
        t2 = NOW + timedelta(seconds=3)
        result = gate.evaluate(
            q(ts=t2), now=NOW + timedelta(seconds=5)
        )
        assert result.status is QualityStatus.STALE

    def test_invalid_env_falls_back(self, monkeypatch):
        monkeypatch.setenv("MARKET_DATA_FRESH_MS", "not-a-number")
        cfg = QualityConfig.from_env()
        assert cfg.fresh_ms == 3000


# --- Per-symbol duplicate counting (§15 drill-down) ---------------------------


class TestDuplicateCount:
    def test_per_symbol_count(self):
        gate = QualityGate()
        t1 = cst(2026, 9, 8, 10, 0)
        gate.evaluate(q(ts=t1), now=t1)
        assert gate.duplicate_count("159852") == 0
        gate.evaluate(q(ts=t1), now=t1)          # dup #1
        gate.evaluate(q(ts=t1), now=t1)          # dup #2
        assert gate.duplicate_count("159852") == 2

    def test_other_symbol_not_affected(self):
        gate = QualityGate()
        t1 = cst(2026, 9, 8, 10, 0)
        gate.evaluate(q(ts=t1), now=t1)
        gate.evaluate(q(ts=t1), now=t1)
        assert gate.duplicate_count("510300") == 0

    def test_reset_clears_counts(self):
        gate = QualityGate()
        t1 = cst(2026, 9, 8, 10, 0)
        gate.evaluate(q(ts=t1), now=t1)
        gate.evaluate(q(ts=t1), now=t1)
        gate.reset()
        assert gate.duplicate_count("159852") == 0


# --- Strategy Gate integration (§16) ---------------------------------------------


class TestStrategyGateIntegration:
    def _service(self):
        from services.market_data.validators.market_data_validator import (
            MarketDataValidator,
        )

        return QuoteService(
            quality_gate=QualityGate(),
            validator=MarketDataValidator(stale_seconds=10**9),
        )

    def test_no_quote_not_tradable(self):
        svc = QuoteService()
        assert svc.tradable("159852") is False

    def test_fresh_quote_tradable(self):
        svc = self._service()
        t = cst(2026, 9, 8, 10, 31)
        svc.update(q(ts=t), now=t)
        # verdict evaluated at write time with the session active
        assert svc.tradable("159852") is True

    def test_rejected_quote_not_tradable(self):
        """Signal BUY → Gate → INVALID → BLOCK: the rejected quote
        never even reaches the latest-quote cache."""
        svc = self._service()
        with pytest.raises(QualityRejectedError):
            svc.update(q(last="-1"))
        assert svc.tradable("159852") is False

    def test_derive_mode_old_quote_not_tradable(self):
        """Without a gate the read path re-derives freshness against
        now — an old stored quote honestly reports not tradable."""
        svc = QuoteService(
            validator=__import__(
                "services.market_data.validators.market_data_validator",
                fromlist=["MarketDataValidator"],
            ).MarketDataValidator(stale_seconds=10**9),
        )
        # quote from long ago within a continuous session
        old = cst(2026, 9, 8, 10, 0)
        svc.update(q(ts=old))
        assert svc.tradable("159852") is False


# --- Pipeline E2E (§18: Quote → Session → Gate → PASS/FAIL) ----------------------


class TestPipelineEndToEnd:
    """The full Commit 006 pipeline::

        Quote → Normalizer → Session → Quality Gate
             → PASS  → Strategy / Paper
             → FAIL  → Quarantine
    """

    def _service(self):
        from services.market_data.validators.market_data_validator import (
            MarketDataValidator,
        )

        gate = QualityGate()
        return (
            QuoteService(
                quality_gate=gate,
                validator=MarketDataValidator(stale_seconds=10**9),
            ),
            gate,
        )

    def test_pass_path(self):
        svc, gate = self._service()
        t = cst(2026, 9, 8, 10, 31)
        stored = svc.update(q(ts=t, volume=1000), now=t)
        # stored → visible to Strategy
        assert svc.latest("159852").last == stored.last
        assert svc.tradable("159852") is True
        # nothing rejected
        assert gate.quarantine.count() == 0
        assert gate.stats()["evaluated"] == 1

    def test_fail_path_goes_to_quarantine(self):
        svc, gate = self._service()
        with pytest.raises(QualityRejectedError):
            svc.update(q(bid="1.235", ask="1.233"))
        # never stored
        assert svc.latest("159852") is None
        # preserved in quarantine with the verdict
        assert gate.quarantine.count() == 1
        item = gate.quarantine.recent()[0]
        assert item["reasons"] == ["CROSSED_BOOK"]
        assert item["status"] == "INVALID"
        # Strategy sees: not tradable
        assert svc.tradable("159852") is False

    def test_duplicate_path_dropped_and_counted(self):
        svc, gate = self._service()
        t = cst(2026, 9, 8, 10, 31)
        svc.update(q(ts=t), now=t)
        with pytest.raises(QualityRejectedError):
            svc.update(q(ts=t), now=t)  # resend
        assert gate.duplicate_count("159852") == 1
        # the original accepted quote is still the latest one
        assert svc.latest("159852") is not None

    def test_stale_valid_data_stored_but_blocked(self):
        """STALE quote: valid data → stored for display, but the
        Strategy Gate blocks it (BLOCK_TRADING, no quarantine)."""
        svc, gate = self._service()
        t = cst(2026, 9, 8, 10, 31)
        stale = q(ts=t - timedelta(seconds=30))
        svc.update(stale, now=t)
        assert svc.latest("159852") is not None
        assert gate.quarantine.count() == 0
        assert svc.tradable("159852") is False


# --- Derive (stateless read path) -----------------------------------------------------


class TestDerive:
    def test_derive_fresh_quote(self):
        gate = QualityGate()
        result = gate.derive(q(ts=NOW), now=NOW)
        assert result.status is QualityStatus.FRESH
        assert result.tradable is True

    def test_derive_flags_session_inactive(self):
        gate = QualityGate()
        lunch = cst(2026, 9, 8, 12, 15)
        result = gate.derive(q(ts=lunch), now=lunch)
        assert "SESSION_INACTIVE" in result.reasons
        assert result.tradable is False

    def test_derive_no_state(self):
        """derive is stateless: same quote twice → same result."""
        gate = QualityGate()
        r1 = gate.derive(q(ts=NOW), now=NOW)
        r2 = gate.derive(q(ts=NOW), now=NOW)
        assert "DUPLICATE" not in r1.reasons
        assert "DUPLICATE" not in r2.reasons
        assert r1.status is r2.status
