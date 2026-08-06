"""Holiday Calendar — holiday and special trading day definitions.

The :class:`HolidayCalendar` tracks holidays, half trading days, and
special makeup trading days per market.  It supports online updates
so holiday schedules can be refreshed without restart.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Set


@dataclass
class Holiday:
    """A single holiday entry."""

    date: date
    name: str
    market: str
    is_half_day: bool = False
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "date": self.date.isoformat(),
            "name": self.name,
            "market": self.market,
            "is_half_day": self.is_half_day,
            "description": self.description,
        }


@dataclass
class HolidayCalendar:
    """Per-market holiday registry with online update support.

    Tracks:
    * Full holidays (market closed)
    * Half trading days (early close)
    * Special makeup trading days (weekend trading)

    Usage::

        cal = HolidayCalendar()
        cal.add_holiday("CN", date(2026, 10, 1), "National Day")
        cal.is_holiday(date(2026, 10, 1), "CN")  # True
    """

    def __init__(self) -> None:
        self._holidays: Dict[str, Dict[date, Holiday]] = {}
        self._half_days: Dict[str, Set[date]] = {}
        self._makeup_days: Dict[str, Set[date]] = {}

    # ------------------------------------------------------------------
    # Holiday CRUD
    # ------------------------------------------------------------------

    def add_holiday(
        self,
        market: str,
        d: date,
        name: str = "",
        is_half_day: bool = False,
        description: str = "",
    ) -> None:
        mkt = market.upper()
        if mkt not in self._holidays:
            self._holidays[mkt] = {}
        self._holidays[mkt][d] = Holiday(
            date=d,
            name=name,
            market=mkt,
            is_half_day=is_half_day,
            description=description,
        )
        if is_half_day:
            self._half_days.setdefault(mkt, set()).add(d)

    def add_holidays_batch(self, market: str, holidays: List[Holiday]) -> None:
        for h in holidays:
            self.add_holiday(h.market or market, h.date, h.name, h.is_half_day, h.description)

    def remove_holiday(self, market: str, d: date) -> bool:
        mkt = market.upper()
        removed = self._holidays.get(mkt, {}).pop(d, None)
        if removed:
            self._half_days.get(mkt, set()).discard(d)
            return True
        return False

    def get_holiday(self, market: str, d: date) -> Optional[Holiday]:
        return self._holidays.get(market.upper(), {}).get(d)

    def get_holidays_in_range(
        self, market: str, start: date, end: date
    ) -> List[Holiday]:
        mkt = market.upper()
        result = []
        for d, h in self._holidays.get(mkt, {}).items():
            if start <= d <= end:
                result.append(h)
        return sorted(result, key=lambda h: h.date)

    # ------------------------------------------------------------------
    # Makeup trading days
    # ------------------------------------------------------------------

    def add_makeup_day(self, market: str, d: date) -> None:
        """Add a special makeup trading day (typically a Saturday/Sunday)."""
        self._makeup_days.setdefault(market.upper(), set()).add(d)

    def is_makeup_day(self, market: str, d: date) -> bool:
        return d in self._makeup_days.get(market.upper(), set())

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def is_holiday(self, dt: datetime, market: str = "CN") -> bool:
        """Check if the given date is a holiday (full day off)."""
        mkt = market.upper()
        d = dt.date() if isinstance(dt, datetime) else dt

        # Makeup days are NOT holidays
        if d in self._makeup_days.get(mkt, set()):
            return False

        h = self._holidays.get(mkt, {}).get(d)
        if h is None:
            return False
        return not h.is_half_day

    def is_half_day(self, dt: datetime, market: str = "CN") -> bool:
        mkt = market.upper()
        d = dt.date() if isinstance(dt, datetime) else dt
        return d in self._half_days.get(mkt, set())

    def get_holiday_count(self, market: str) -> int:
        return len(self._holidays.get(market.upper(), {}))

    def get_all_holidays(self, market: str) -> List[Holiday]:
        return sorted(
            self._holidays.get(market.upper(), {}).values(),
            key=lambda h: h.date,
        )

    # ------------------------------------------------------------------
    # Online update
    # ------------------------------------------------------------------

    def update_from_dict(self, data: Dict[str, Any]) -> None:
        """Bulk-update holidays from a dict (e.g., fetched from API)."""
        for market, entries in data.items():
            for entry in entries:
                self.add_holiday(
                    market=market,
                    d=date.fromisoformat(entry["date"]),
                    name=entry.get("name", ""),
                    is_half_day=entry.get("is_half_day", False),
                    description=entry.get("description", ""),
                )

    def clear(self, market: Optional[str] = None) -> None:
        """Clear holidays for a market or all markets."""
        if market:
            self._holidays.pop(market.upper(), None)
            self._half_days.pop(market.upper(), None)
            self._makeup_days.pop(market.upper(), None)
        else:
            self._holidays.clear()
            self._half_days.clear()
            self._makeup_days.clear()

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "markets": {
                mkt: {
                    "holiday_count": len(holidays),
                    "half_day_count": len(self._half_days.get(mkt, set())),
                    "makeup_count": len(self._makeup_days.get(mkt, set())),
                }
                for mkt, holidays in self._holidays.items()
            }
        }
