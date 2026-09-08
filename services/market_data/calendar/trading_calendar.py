"""A-share Trading Calendar (Commit 005).

Separates Trading Day from Calendar Day:

- Weekend rule: Sat/Sun are non-trading **unless** they are makeup
  trading days (调休上班日).
- Holiday rule: declared holidays are non-trading even on weekdays.

All phase computation uses China Standard Time (UTC+8, no DST).  A-share
fund trading hours are identical across SSE / SZSE, so the calendar
serves both exchanges; per-instrument-type rules can extend
``is_tradable(ts, instrument)`` later.

Core interface::

    calendar.is_trading_day("2026-09-08")     → True
    calendar.is_trading_day("2026-09-06")     → False (Sunday)
    calendar.get_phase(ts)                    → MarketPhase
    calendar.get_session(ts, exchange)         → TradingSession
    calendar.is_tradable(ts)                  → bool (Strategy Gate)
    calendar.next_event(ts)                   → (phase, at)
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Optional, Union

from ..domain.instrument import Exchange
from .market_phase import (
    PHASE_LABELS,
    MarketPhase,
)
from .session import TradingSession

# China Standard Time: UTC+8, no daylight saving.
CST = timezone(timedelta(hours=8), "Asia/Shanghai")

# ---------------------------------------------------------------------------
# 2026 holiday schedule (provisional data mirroring the State Council
# pattern; update from the official announcement when published).
# Weekday holidays: non-trading even though they are workweek days.
# ---------------------------------------------------------------------------
_HOLIDAYS_2026: set[date] = {
    # 元旦 (Jan 1 Thu – Jan 3 Sat)
    date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3),
    # 春节 (Feb 16 Mon – Feb 22 Sun, 除夕 Feb 16)
    *[date(2026, 2, d) for d in range(16, 23)],
    # 清明节 (Apr 4 Sat – Apr 6 Mon)
    *[date(2026, 4, d) for d in range(4, 7)],
    # 劳动节 (May 1 Fri – May 5 Tue)
    *[date(2026, 5, d) for d in range(1, 6)],
    # 端午节 (Jun 19 Fri – Jun 21 Sun)
    *[date(2026, 6, d) for d in range(19, 22)],
    # 中秋节 (Sep 25 Fri – Sep 27 Sun)
    *[date(2026, 9, d) for d in range(25, 28)],
    # 国庆节 (Oct 1 Thu – Oct 7 Wed)
    *[date(2026, 10, d) for d in range(1, 8)],
}

# 调休 makeup trading days: weekend sessions where the market IS open.
_MAKEUP_DAYS_2026: set[date] = {
    date(2026, 2, 28),   # Sat — Spring Festival makeup
    date(2026, 5, 9),    # Sat — Labour Day makeup
    date(2026, 10, 10),  # Sat — National Day makeup
}


# ---------------------------------------------------------------------------
# Phase segments on a trading day (CST wall-clock, [start, end))
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class _Segment:
    start: time
    end: time
    phase: MarketPhase


_SEGMENTS: list[_Segment] = [
    _Segment(time(0, 0), time(9, 20), MarketPhase.PRE_OPEN),
    _Segment(time(9, 20), time(9, 30), MarketPhase.AUCTION),
    _Segment(time(9, 30), time(11, 30), MarketPhase.CONTINUOUS_AM),
    _Segment(time(11, 30), time(13, 0), MarketPhase.LUNCH_BREAK),
    _Segment(time(13, 0), time(15, 0), MarketPhase.CONTINUOUS_PM),
    _Segment(time(15, 0), time(15, 5), MarketPhase.CLOSE),
    _Segment(time(15, 5), time(23, 59, 59), MarketPhase.POST_CLOSE),
]


def _to_cst(ts: datetime) -> datetime:
    """Convert a tz-aware datetime to CST (naive treated as UTC)."""
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts.astimezone(CST)


def _coerce_date(value: Union[date, datetime, str]) -> date:
    if isinstance(value, datetime):
        return _to_cst(value).date()
    if isinstance(value, str):
        return date.fromisoformat(value)
    return value


class TradingCalendar:
    """A-share trading calendar + session engine."""

    def __init__(
        self,
        *,
        holidays: Optional[set[date]] = None,
        makeup_days: Optional[set[date]] = None,
    ) -> None:
        self._holidays = set(holidays) if holidays else set(_HOLIDAYS_2026)
        self._makeups = set(makeup_days) if makeup_days else set(
            _MAKEUP_DAYS_2026
        )

    # ── trading day ─────────────────────────────────────────────

    def is_trading_day(self, value: Union[date, datetime, str]) -> bool:
        """True when the market is open for that date.

        Weekend → False unless it is a makeup trading day.
        Weekday → False when it is a declared holiday.
        """
        d = _coerce_date(value)
        if d.weekday() >= 5:  # Sat/Sun
            return d in self._makeups
        return d not in self._holidays

    def next_trading_day(self, value: Union[date, datetime, str]) -> date:
        """First trading day strictly after the given date."""
        d = _coerce_date(value) + timedelta(days=1)
        while not self.is_trading_day(d):
            d += timedelta(days=1)
        return d

    def trading_date_of(self, ts: datetime) -> date:
        """CST calendar date of a timestamp."""
        return _to_cst(ts).date()

    # ── phase / session ──────────────────────────────────────────

    def get_phase(
        self, ts: datetime, exchange: Optional[Exchange] = None
    ) -> MarketPhase:
        """Market phase at a timestamp (Strategy / bar gating)."""
        local = _to_cst(ts)
        if not self.is_trading_day(local.date()):
            return MarketPhase.NON_TRADING
        t = local.time()
        for seg in _SEGMENTS:
            if seg.start <= t < seg.end:
                return seg.phase
        return MarketPhase.POST_CLOSE

    def get_session(
        self,
        ts: datetime,
        exchange: Exchange = Exchange.SZSE,
    ) -> TradingSession:
        """TradingSession for the phase segment containing ``ts``."""
        local = _to_cst(ts)
        trading_day = self.is_trading_day(local.date())
        phase = self.get_phase(ts, exchange)

        if not trading_day or phase == MarketPhase.NON_TRADING:
            return TradingSession(
                trading_date=local.date(),
                exchange=exchange,
                phase=MarketPhase.NON_TRADING,
                session_start=None,
                session_end=None,
                is_trading_day=False,
            )

        for seg in _SEGMENTS:
            if seg.start <= local.time() < seg.end:
                return TradingSession(
                    trading_date=local.date(),
                    exchange=exchange,
                    phase=seg.phase,
                    session_start=datetime.combine(
                        local.date(), seg.start, CST
                    ),
                    session_end=datetime.combine(
                        local.date(), seg.end, CST
                    ),
                    is_trading_day=True,
                )
        # unreachable (segments cover the full day)
        raise RuntimeError("no phase segment matched")

    # ── gates ───────────────────────────────────────────────────

    def is_tradable(
        self, ts: datetime, instrument: object = None
    ) -> bool:
        """Strategy Gate: can continuous trading happen right now?

        Phase 1: all universe instrument types share the same
        schedule; ``instrument`` is accepted for future per-type
        rules (e.g. different auction windows).
        """
        return self.get_phase(ts) in (
            MarketPhase.CONTINUOUS_AM,
            MarketPhase.CONTINUOUS_PM,
        )

    def is_bar_phase(self, ts: datetime) -> bool:
        """True when 1m bars should be aggregated for a timestamp."""
        return self.get_phase(ts) in (
            MarketPhase.CONTINUOUS_AM,
            MarketPhase.CONTINUOUS_PM,
        )

    # ── navigation ───────────────────────────────────────────────

    def next_event(
        self, ts: datetime
    ) -> tuple[MarketPhase, datetime]:
        """The next phase transition after ``ts`` (CST-aware)."""
        local = _to_cst(ts)

        if not self.is_trading_day(local.date()):
            nd = self.next_trading_day(local.date())
            return (
                MarketPhase.AUCTION,
                datetime.combine(nd, time(9, 20), CST),
            )

        for i, seg in enumerate(_SEGMENTS):
            if seg.start <= local.time() < seg.end:
                if i + 1 < len(_SEGMENTS):
                    nxt = _SEGMENTS[i + 1]
                    return (
                        nxt.phase,
                        datetime.combine(local.date(), seg.end, CST),
                    )
                # Last segment of the day → next trading day open
                nd = self.next_trading_day(local.date())
                return (
                    MarketPhase.AUCTION,
                    datetime.combine(nd, time(9, 20), CST),
                )

        # exact 23:59:59+ edge — treat as end of day
        nd = self.next_trading_day(local.date())
        return (
            MarketPhase.AUCTION,
            datetime.combine(nd, time(9, 20), CST),
        )

    # ── API view ─────────────────────────────────────────────────

    def status(
        self,
        ts: Optional[datetime] = None,
        exchange: Exchange = Exchange.SZSE,
    ) -> dict:
        """Aggregated market status payload for the Dashboard."""
        now = ts or datetime.now(timezone.utc)
        session = self.get_session(now, exchange)
        nphase, nat = self.next_event(now)
        return {
            "market": "A-SHARE",
            "phase": session.phase.value,
            "phase_label": session.phase_label,
            "is_trading_day": session.is_trading_day,
            "is_tradable": session.is_tradable,
            "trading_date": session.trading_date.isoformat(),
            "session": {
                "start": (
                    session.session_start.isoformat()
                    if session.session_start
                    else None
                ),
                "end": (
                    session.session_end.isoformat()
                    if session.session_end
                    else None
                ),
            },
            "next_event": {
                "phase": nphase.value,
                "label": PHASE_LABELS.get(nphase.value, nphase.value),
                "at": nat.isoformat(),
            },
            "server_time": now.isoformat(),
            "timezone": "Asia/Shanghai (UTC+8)",
        }


# ── Singleton ─────────────────────────────────────────────────
calendar = TradingCalendar()

__all__ = ["TradingCalendar", "calendar", "CST"]
