"""Tests for the A-share Trading Calendar / Session engine (Commit 005).

Gate: Trading day detection, Weekend detection, Holiday detection,
Make-up trading day, Phase transitions, Session model, Strategy gate
(is_tradable), Next event, Bar ↔ session integration (lunch break
produces no bar, closures are not gaps, day-boundary volume reset).
"""
from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from services.market_data.aggregation.bar_service import BarService
from services.market_data.calendar.market_phase import (
    BAR_PHASES,
    TRADABLE_PHASES,
    MarketPhase,
)
from services.market_data.calendar.session import TradingSession
from services.market_data.calendar.trading_calendar import (
    CST,
    TradingCalendar,
    calendar,
)
from services.market_data.domain.instrument import Exchange
from services.market_data.domain.quote import MarketQuote


def cst(y: int, m: int, d: int, h: int = 0, mi: int = 0, s: int = 0) -> datetime:
    """A timezone-aware China Standard Time datetime."""
    return datetime(y, m, d, h, mi, s, tzinfo=CST)


def _q(
    ts: datetime,
    last: str = "1.000",
    volume: int = 0,
    symbol: str = "159852",
) -> MarketQuote:
    return MarketQuote(
        symbol=symbol,
        exchange=Exchange.SZSE,
        timestamp=ts,
        last=Decimal(last),
        bid=Decimal(last),
        ask=Decimal(last),
        bid_size=10000,
        ask_size=10000,
        volume=volume,
        turnover=Decimal("0"),
    )


# --- Trading day detection ---------------------------------------------------


class TestTradingDayDetection:
    def test_weekday_is_trading_day(self):
        assert calendar.is_trading_day("2026-09-08") is True  # Tue

    def test_saturday_is_not(self):
        assert calendar.is_trading_day("2026-09-05") is False

    def test_sunday_is_not(self):
        assert calendar.is_trading_day("2026-09-06") is False

    def test_date_object_and_string_agree(self):
        assert calendar.is_trading_day(cst(2026, 9, 8)) is True
        assert calendar.is_trading_day(cst(2026, 9, 8).date()) is True

    def test_holiday_weekday_is_not(self):
        # National Day (Thu) — a workweek day but the market is closed
        assert calendar.is_trading_day("2026-10-01") is False
        # Mid-Autumn (Fri)
        assert calendar.is_trading_day("2026-09-25") is False
        # Spring Festival (Mon)
        assert calendar.is_trading_day("2026-02-16") is False

    def test_makeup_saturday_is_trading_day(self):
        assert calendar.is_trading_day("2026-02-28") is True  # Spring makeup
        assert calendar.is_trading_day("2026-05-09") is True  # Labour makeup
        assert calendar.is_trading_day("2026-10-10") is True  # National makeup

    def test_next_trading_day_skips_weekend(self):
        # Fri 2026-09-04 → Mon 2026-09-07
        assert calendar.next_trading_day("2026-09-04").isoformat() == "2026-09-07"

    def test_next_trading_day_skips_holiday_block(self):
        # Last National Day holiday slot 2026-10-07 (Wed) → 2026-10-08
        assert calendar.next_trading_day("2026-10-07").isoformat() == "2026-10-08"

    def test_next_trading_day_from_holiday_eve(self):
        # Thu 2026-09-24 (trading) is followed by the Mid-Autumn block
        assert calendar.next_trading_day("2026-09-24").isoformat() == "2026-09-28"


# --- Market phase on a trading day -------------------------------------------


class TestPhaseTransitions:
    """2026-09-08 (Tue) — a normal trading day, CST wall clock."""

    @pytest.mark.parametrize(
        "h,m,expected",
        [
            (9, 15, MarketPhase.PRE_OPEN),
            (9, 19, MarketPhase.PRE_OPEN),
            (9, 20, MarketPhase.AUCTION),
            (9, 29, MarketPhase.AUCTION),
            (9, 30, MarketPhase.CONTINUOUS_AM),
            (11, 29, MarketPhase.CONTINUOUS_AM),
            (11, 30, MarketPhase.LUNCH_BREAK),
            (12, 45, MarketPhase.LUNCH_BREAK),
            (13, 0, MarketPhase.CONTINUOUS_PM),
            (14, 59, MarketPhase.CONTINUOUS_PM),
            (15, 0, MarketPhase.CLOSE),
            (15, 4, MarketPhase.CLOSE),
            (15, 5, MarketPhase.POST_CLOSE),
            (23, 0, MarketPhase.POST_CLOSE),
        ],
    )
    def test_phase_at(self, h: int, m: int, expected: MarketPhase):
        assert calendar.get_phase(cst(2026, 9, 8, h, m)) is expected

    def test_auction_not_confused_with_continuous(self):
        """09:20 quotes must read AUCTION, not CONTINUOUS_AM."""
        assert calendar.get_phase(cst(2026, 9, 8, 9, 20)) is MarketPhase.AUCTION
        assert calendar.get_phase(cst(2026, 9, 8, 9, 30)) is MarketPhase.CONTINUOUS_AM

    def test_utc_input_converted_to_cst(self):
        # 02:00 UTC == 10:00 CST → CONTINUOUS_AM
        from datetime import timezone

        assert (
            calendar.get_phase(datetime(2026, 9, 8, 2, 0, tzinfo=timezone.utc))
            is MarketPhase.CONTINUOUS_AM
        )


class TestPhaseOnNonTradingDay:
    def test_weekend_phase(self):
        assert calendar.get_phase(cst(2026, 9, 6, 10, 0)) is MarketPhase.NON_TRADING

    def test_holiday_phase(self):
        assert calendar.get_phase(cst(2026, 10, 1, 10, 0)) is MarketPhase.NON_TRADING

    def test_makeup_saturday_has_normal_phases(self):
        assert (
            calendar.get_phase(cst(2026, 2, 28, 10, 0))
            is MarketPhase.CONTINUOUS_AM
        )


# --- Strategy gate: is_tradable ----------------------------------------------


class TestStrategyGate:
    @pytest.mark.parametrize(
        "h,m,expected",
        [
            (9, 29, False),   # still auction
            (9, 30, True),    # continuous opens
            (11, 29, True),
            (11, 45, False),  # lunch break
            (13, 0, True),    # afternoon reopens
            (15, 0, False),   # close
            (15, 1, False),
            (9, 20, False),   # auction — quotes flow, trading not allowed
        ],
    )
    def test_is_tradable_gates(self, h: int, m: int, expected: bool):
        assert calendar.is_tradable(cst(2026, 9, 8, h, m)) is expected

    def test_non_trading_day_never_tradable(self):
        assert calendar.is_tradable(cst(2026, 9, 6, 10, 0)) is False

    def test_makeup_saturday_tradable(self):
        assert calendar.is_tradable(cst(2026, 2, 28, 10, 0)) is True

    def test_is_bar_phase_matches_tradable(self):
        """1m bars only aggregate during continuous phases."""
        assert calendar.is_bar_phase(cst(2026, 9, 8, 10, 0)) is True
        assert calendar.is_bar_phase(cst(2026, 9, 8, 12, 0)) is False
        assert calendar.is_bar_phase(cst(2026, 9, 8, 9, 20)) is False
        assert calendar.is_bar_phase(cst(2026, 9, 6, 10, 0)) is False


# --- Session model ------------------------------------------------------------


class TestTradingSessionModel:
    def test_continuous_am_session(self):
        s = calendar.get_session(cst(2026, 9, 8, 10, 0))
        assert isinstance(s, TradingSession)
        assert s.trading_date.isoformat() == "2026-09-08"
        assert s.exchange is Exchange.SZSE
        assert s.market == "A-SHARE"
        assert s.phase is MarketPhase.CONTINUOUS_AM
        assert s.session_start == cst(2026, 9, 8, 9, 30)
        assert s.session_end == cst(2026, 9, 8, 11, 30)
        assert s.is_trading_day is True
        assert s.is_tradable is True

    def test_lunch_break_session(self):
        s = calendar.get_session(cst(2026, 9, 8, 12, 0))
        assert s.phase is MarketPhase.LUNCH_BREAK
        assert s.session_start == cst(2026, 9, 8, 11, 30)
        assert s.session_end == cst(2026, 9, 8, 13, 0)
        assert s.is_trading_day is True
        assert s.is_tradable is False

    def test_non_trading_session(self):
        s = calendar.get_session(cst(2026, 9, 6, 12, 0))
        assert s.phase is MarketPhase.NON_TRADING
        assert s.is_trading_day is False
        assert s.is_tradable is False
        assert s.session_start is None
        assert s.session_end is None

    def test_session_as_dict(self):
        s = calendar.get_session(cst(2026, 9, 8, 10, 0))
        d = s.as_dict()
        for key in (
            "trading_date", "exchange", "market", "phase", "phase_label",
            "session_start", "session_end", "is_trading_day", "is_tradable",
        ):
            assert key in d, f"missing {key}"
        assert d["is_tradable"] is True


# --- Next event ---------------------------------------------------------------


class TestNextEvent:
    def test_morning_to_lunch(self):
        phase, at = calendar.next_event(cst(2026, 9, 8, 11, 0))
        assert phase is MarketPhase.LUNCH_BREAK
        assert at == cst(2026, 9, 8, 11, 30)

    def test_lunch_to_afternoon(self):
        phase, at = calendar.next_event(cst(2026, 9, 8, 12, 0))
        assert phase is MarketPhase.CONTINUOUS_PM
        assert at == cst(2026, 9, 8, 13, 0)

    def test_preopen_to_auction(self):
        phase, at = calendar.next_event(cst(2026, 9, 8, 9, 0))
        assert phase is MarketPhase.AUCTION
        assert at == cst(2026, 9, 8, 9, 20)

    def test_after_close_rolls_to_next_trading_day(self):
        # Fri 16:00 → next Monday 09:20
        phase, at = calendar.next_event(cst(2026, 9, 4, 16, 0))
        assert phase is MarketPhase.AUCTION
        assert at == cst(2026, 9, 7, 9, 20)

    def test_non_trading_day_rolls_to_next_trading_day(self):
        # Sunday 2026-09-06 → Monday 09:20
        phase, at = calendar.next_event(cst(2026, 9, 6, 12, 0))
        assert phase is MarketPhase.AUCTION
        assert at == cst(2026, 9, 7, 9, 20)

    def test_holiday_rolls_over_block(self):
        # Wed 2026-10-07 (last National Day holiday) → Thu 10-08 09:20
        phase, at = calendar.next_event(cst(2026, 10, 7, 12, 0))
        assert phase is MarketPhase.AUCTION
        assert at == cst(2026, 10, 8, 9, 20)


# --- Status payload (Dashboard view) ------------------------------------------


class TestStatusPayload:
    def test_status_shape(self):
        body = calendar.status(cst(2026, 9, 8, 10, 0))
        for key in (
            "market", "phase", "phase_label", "is_trading_day",
            "is_tradable", "trading_date", "session", "next_event",
            "server_time", "timezone",
        ):
            assert key in body, f"missing {key}"
        assert body["market"] == "A-SHARE"
        assert body["phase"] == "CONTINUOUS_AM"
        assert body["is_tradable"] is True
        assert body["session"]["start"].startswith("2026-09-08T09:30")
        assert body["session"]["end"].startswith("2026-09-08T11:30")
        assert body["next_event"]["phase"] == "LUNCH_BREAK"

    def test_status_lunch(self):
        body = calendar.status(cst(2026, 9, 8, 12, 0))
        assert body["phase"] == "LUNCH_BREAK"
        assert body["is_tradable"] is False
        assert body["next_event"]["phase"] == "CONTINUOUS_PM"

    def test_status_closed(self):
        body = calendar.status(cst(2026, 9, 8, 16, 0))
        assert body["phase"] == "POST_CLOSE"
        assert body["is_tradable"] is False
        assert body["next_event"]["phase"] == "AUCTION"

    def test_status_non_trading(self):
        body = calendar.status(cst(2026, 9, 6, 12, 0))
        assert body["phase"] == "NON_TRADING"
        assert body["is_trading_day"] is False


# --- Bar ↔ Session integration -------------------------------------------------


class TestBarSessionIntegration:
    """Commit 004 aggregator × Commit 005 calendar."""

    def test_lunch_quotes_do_not_form_bars(self):
        svc = BarService(enforce_session=True)
        # 12:00 lunch quote → skipped entirely
        assert svc.on_quote(_q(cst(2026, 9, 8, 12, 0))) is None
        assert svc.current_bar("159852") is None
        assert svc.bar_count("159852") == 0

    def test_auction_quotes_do_not_form_bars(self):
        svc = BarService(enforce_session=True)
        assert svc.on_quote(_q(cst(2026, 9, 8, 9, 20))) is None
        assert svc.current_bar("159852") is None

    def test_non_trading_day_quotes_do_not_form_bars(self):
        svc = BarService(enforce_session=True)
        assert svc.on_quote(_q(cst(2026, 9, 6, 10, 0))) is None  # Sunday
        assert svc.current_bar("159852") is None

    def test_lunch_is_not_a_gap(self):
        """11:29 bar → 13:00 bar: the lunch minutes are closures, not
        missing data."""
        svc = BarService(enforce_session=True)
        svc.on_quote(_q(cst(2026, 9, 8, 11, 29, 30)))
        result = svc.on_quote(_q(cst(2026, 9, 8, 13, 0, 30)))
        assert result is not None
        closed, gaps = result
        assert closed.timestamp == cst(2026, 9, 8, 11, 29)
        assert gaps == []  # 90 lunch minutes filtered out
        assert svc.gaps("159852") == []

    def test_real_gap_still_detected(self):
        """A gap inside continuous trading is still a data gap."""
        svc = BarService(enforce_session=True)
        svc.on_quote(_q(cst(2026, 9, 8, 9, 31)))
        result = svc.on_quote(_q(cst(2026, 9, 8, 9, 35)))
        assert result is not None
        _closed, gaps = result
        assert len(gaps) == 3  # 09:32, 09:33, 09:34

    def test_day_boundary_volume_resets(self):
        """Cumulative volume never crosses a trading-day boundary."""
        svc = BarService(enforce_session=True)
        # Day 1 afternoon, cumulative volume 10000
        svc.on_quote(_q(cst(2026, 9, 8, 14, 59), volume=10000))
        # Day 2 morning: cumulative reset to 500
        result = svc.on_quote(_q(cst(2026, 9, 9, 9, 31), volume=500))
        assert result is not None
        day1_bar, gaps = result
        assert day1_bar.timestamp == cst(2026, 9, 8, 14, 59)
        # Day 2 bar accumulates from the fresh baseline
        svc.on_quote(_q(cst(2026, 9, 9, 9, 31, 30), volume=600))
        day2_bar = svc.current_bar("159852")
        assert day2_bar.volume == 100  # 600 - 500, not 600 - 10000

    def test_default_service_stays_always_on(self):
        """The singleton (mock feed) does not enforce the session —
        the market data connection stays up through lunch; the
        TradingSession layer, not the feed, decides tradability."""
        svc = BarService()
        svc.on_quote(_q(cst(2026, 9, 8, 12, 0)))
        assert svc.current_bar("159852") is not None  # lunch bar formed


# --- Phase classification ------------------------------------------------------


class TestPhaseClassification:
    def test_tradable_phases(self):
        assert TRADABLE_PHASES == frozenset(
            {MarketPhase.CONTINUOUS_AM, MarketPhase.CONTINUOUS_PM}
        )

    def test_bar_phases_match_tradable(self):
        assert BAR_PHASES == TRADABLE_PHASES

    def test_all_phases_present(self):
        names = {p.value for p in MarketPhase}
        assert names == {
            "PRE_OPEN", "AUCTION", "CONTINUOUS_AM", "LUNCH_BREAK",
            "CONTINUOUS_PM", "CLOSE", "POST_CLOSE", "NON_TRADING",
        }
