"""Market Calendar — unified market calendar aggregating trading + session + holiday.

The :class:`MarketCalendar` is the single entry point for calendar queries.
It composes :class:`TradingCalendar`, :class:`SessionCalendar`, and
:class:`HolidayCalendar` into one coherent interface for the scheduler.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

from .trading_calendar import TradingCalendar, Market
from .session_calendar import SessionCalendar, TradingSession
from .holiday_calendar import HolidayCalendar


@dataclass
class MarketCalendar:
    """Unified market calendar for scheduler queries.

    Composes three calendars:
    * TradingCalendar — which days are trading days
    * SessionCalendar — intraday session time windows
    * HolidayCalendar — holiday and special-day definitions

    Usage::

        cal = MarketCalendar()
        cal.is_trading_day(now, "CN")     # True if today is a trading day
        cal.is_in_session(now, "CN")      # True if in active session
        cal.is_holiday(now, "CN")         # True if today is a holiday
    """

    trading: TradingCalendar = field(default_factory=TradingCalendar)
    session: SessionCalendar = field(default_factory=SessionCalendar)
    holiday: HolidayCalendar = field(default_factory=HolidayCalendar)

    # ------------------------------------------------------------------
    # Trading day
    # ------------------------------------------------------------------

    def is_trading_day(self, dt: datetime, market: str = "CN") -> bool:
        return self.trading.is_trading_day(dt, market)

    def is_half_day(self, dt: datetime, market: str = "CN") -> bool:
        return self.trading.is_half_day(dt, market) or self.holiday.is_half_day(dt, market)

    def get_next_trading_day(
        self, from_dt: Optional[datetime] = None, market: str = "CN"
    ) -> "datetime":
        d = self.trading.get_next_trading_day(from_dt, market)
        return datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)

    def get_previous_trading_day(
        self, from_dt: Optional[datetime] = None, market: str = "CN"
    ) -> "datetime":
        d = self.trading.get_previous_trading_day(from_dt, market)
        return datetime.combine(d, datetime.min.time(), tzinfo=timezone.utc)

    def get_trading_days_in_range(
        self, start: "date", end: "date", market: str = "CN"
    ) -> List["date"]:
        import datetime as dt_mod
        return self.trading.get_trading_days_in_range(start, end, market)

    # ------------------------------------------------------------------
    # Session
    # ------------------------------------------------------------------

    def is_in_session(
        self, dt: datetime, market: str = "CN", session: str = "CONTINUOUS"
    ) -> bool:
        return self.session.is_in_session(dt, market, session)

    def get_current_session(
        self, dt: Optional[datetime] = None, market: str = "CN"
    ) -> Optional[str]:
        return self.session.get_current_session(dt, market)

    def get_next_trading_time(
        self, market: str = "CN", session: str = "CONTINUOUS"
    ) -> Optional[datetime]:
        """Return the next time when the given market+session is active."""
        now = datetime.now(timezone.utc)
        # First check today
        next_start = self.session.get_next_session_start(now, market, session)
        if next_start is None:
            return None

        # Advance until we hit a trading day
        for _ in range(30):
            if self.is_trading_day(next_start, market):
                return next_start
            next_start += timedelta(days=1)
        return None

    def get_session_times(self, market: str, session: str) -> Dict[str, Any]:
        return self.session.get_session_times(market, session)

    # ------------------------------------------------------------------
    # Holiday
    # ------------------------------------------------------------------

    def is_holiday(self, dt: datetime, market: str = "CN") -> bool:
        return self.holiday.is_holiday(dt, market)

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "trading": self.trading.health_report(),
            "session": self.session.health_report(),
            "holiday": self.holiday.health_report(),
        }
