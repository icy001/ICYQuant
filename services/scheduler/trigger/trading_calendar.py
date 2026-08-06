"""Trading Calendar — market-specific trading day definitions.

The :class:`TradingCalendar` defines which days are trading days for a
given market.  Supports CN (China A-shares), US (NYSE/NASDAQ), HK (HKEX),
Crypto (24/7), and custom markets.

Each market has:
* Trading days (Mon-Fri typically, excluding holidays)
* Half trading days
* Special trading days (e.g., weekend makeup days)
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import date, datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Set


class Market(str, enum.Enum):
    """Supported financial markets."""

    CN = "CN"       # China A-shares (SSE / SZSE)
    US = "US"       # US equities (NYSE / NASDAQ)
    HK = "HK"       # Hong Kong (HKEX)
    JP = "JP"       # Japan (TSE)
    UK = "UK"       # UK (LSE)
    EU = "EU"       # Europe (Euronext / Xetra)
    CRYPTO = "CRYPTO"  # Crypto (24/7)
    CUSTOM = "CUSTOM"


@dataclass
class TradingCalendar:
    """Per-market trading day definitions.

    Maintains sets of holidays, half-days, and special trading days for
    each supported market.  Supports adding/removing entries dynamically
    and checking whether a given date is a trading day.

    Usage::

        cal = TradingCalendar()
        cal.add_holiday("CN", date(2026, 1, 1))   # New Year
        cal.is_trading_day(date(2026, 1, 1), "CN")  # False
    """

    # Default weekend days for each market
    _WEEKENDS: Dict[str, Set[int]] = field(default_factory=lambda: {
        Market.CN: {5, 6},   # Sat, Sun
        Market.US: {5, 6},
        Market.HK: {5, 6},
        Market.JP: {5, 6},
        Market.UK: {5, 6},
        Market.EU: {5, 6},
        Market.CRYPTO: set(),  # No weekends for crypto
    })

    def __init__(self) -> None:
        self._holidays: Dict[str, Set[date]] = {m.value: set() for m in Market}
        self._half_days: Dict[str, Set[date]] = {m.value: set() for m in Market}
        self._special_trading_days: Dict[str, Set[date]] = {
            m.value: set() for m in Market
        }

    # ------------------------------------------------------------------
    # Holiday management
    # ------------------------------------------------------------------

    def add_holiday(self, market: str, d: date) -> None:
        self._holidays[market.upper()].add(d)

    def add_holidays(self, market: str, days: List[date]) -> None:
        self._holidays[market.upper()].update(days)

    def remove_holiday(self, market: str, d: date) -> None:
        self._holidays[market.upper()].discard(d)

    def get_holidays(self, market: str) -> List[date]:
        return sorted(self._holidays[market.upper()])

    # ------------------------------------------------------------------
    # Half-day management
    # ------------------------------------------------------------------

    def add_half_day(self, market: str, d: date) -> None:
        self._half_days[market.upper()].add(d)

    def get_half_days(self, market: str) -> List[date]:
        return sorted(self._half_days[market.upper()])

    # ------------------------------------------------------------------
    # Special trading days (weekend makeup)
    # ------------------------------------------------------------------

    def add_special_trading_day(self, market: str, d: date) -> None:
        """Add a special trading day (e.g., Saturday makeup for a holiday)."""
        self._special_trading_days[market.upper()].add(d)

    def get_special_trading_days(self, market: str) -> List[date]:
        return sorted(self._special_trading_days[market.upper()])

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    def is_trading_day(self, dt: datetime, market: str = "CN") -> bool:
        """Check if the given datetime falls on a trading day."""
        mkt = market.upper()
        d = dt.date() if isinstance(dt, datetime) else dt

        # Special trading days override everything
        if d in self._special_trading_days[mkt]:
            return True

        # Holidays are always non-trading
        if d in self._holidays[mkt]:
            return False

        # Check weekend
        weekends = self._WEEKENDS.get(mkt, {5, 6})
        if d.weekday() in weekends:
            return False

        return True

    def is_half_day(self, dt: datetime, market: str = "CN") -> bool:
        mkt = market.upper()
        d = dt.date() if isinstance(dt, datetime) else dt
        return d in self._half_days[mkt]

    def get_next_trading_day(self, from_dt: Optional[datetime] = None, market: str = "CN") -> date:
        """Return the next trading day from *from_dt* (or today)."""
        current = (from_dt or datetime.now(timezone.utc)).date()
        for _ in range(30):  # search up to 30 days
            current += timedelta(days=1)
            if self.is_trading_day(current, market):
                return current
        return current  # fallback

    def get_previous_trading_day(self, from_dt: Optional[datetime] = None, market: str = "CN") -> date:
        """Return the previous trading day before *from_dt* (or today)."""
        current = (from_dt or datetime.now(timezone.utc)).date()
        for _ in range(30):
            current -= timedelta(days=1)
            if self.is_trading_day(current, market):
                return current
        return current

    def get_trading_days_in_range(
        self, start: date, end: date, market: str = "CN"
    ) -> List[date]:
        """Return all trading days between *start* and *end* (inclusive)."""
        mkt = market.upper()
        result = []
        current = start
        while current <= end:
            if self.is_trading_day(current, mkt):
                result.append(current)
            current += timedelta(days=1)
        return result

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_dict(self, market: Optional[str] = None) -> Dict[str, Any]:
        markets = [market.upper()] if market else [m.value for m in Market]
        return {
            m: {
                "holidays": [d.isoformat() for d in sorted(self._holidays[m])],
                "half_days": [d.isoformat() for d in sorted(self._half_days[m])],
                "special_trading_days": [
                    d.isoformat() for d in sorted(self._special_trading_days[m])
                ],
            }
            for m in markets
        }

    def health_report(self) -> Dict[str, Any]:
        return {
            "markets": {
                m.value: {
                    "holiday_count": len(self._holidays[m.value]),
                    "half_day_count": len(self._half_days[m.value]),
                    "special_count": len(self._special_trading_days[m.value]),
                }
                for m in Market
            }
        }
