"""
Timezone Converter — handles conversion between exchange local time,
UTC, and user-specified timezones.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

import pytz

logger = logging.getLogger(__name__)


@dataclass
class MarketTimezone:
    """Market timezone configuration."""
    exchange_id: str = ""
    iana_timezone: str = "UTC"
    trading_start: str = "09:00"
    trading_end: str = "17:00"
    trading_days: list[int] = field(default_factory=lambda: [0, 1, 2, 3, 4])


class TimezoneConverter:
    """
    Converts timestamps between timezones.

    All internal timestamps are stored as UTC nanoseconds.
    This converter handles display conversion for any IANA timezone.
    """

    UTC = timezone.utc

    # Exchange → IANA timezone mapping
    EXCHANGE_TIMEZONES: dict[str, str] = {
        "NYSE": "America/New_York",
        "NASDAQ": "America/New_York",
        "AMEX": "America/New_York",
        "BATS": "America/New_York",
        "ARCA": "America/New_York",
        "CBOE": "America/Chicago",
        "CME": "America/Chicago",
        "CBOT": "America/Chicago",
        "LSE": "Europe/London",
        "XETRA": "Europe/Berlin",
        "EURONEXT": "Europe/Paris",
        "SIX": "Europe/Zurich",
        "TSE": "Asia/Tokyo",
        "OSE": "Asia/Tokyo",
        "HKEX": "Asia/Hong_Kong",
        "SGX": "Asia/Singapore",
        "ASX": "Australia/Sydney",
        "KRX": "Asia/Seoul",
        "SSE": "Asia/Shanghai",
        "SZSE": "Asia/Shanghai",
        "NSE": "Asia/Kolkata",
        "BSE": "Asia/Kolkata",
        "B3": "America/Sao_Paulo",
        "TSX": "America/Toronto",
        "MOEX": "Europe/Moscow",
    }

    async def convert_to_exchange_time(
        self, utc_ns: int, exchange_id: str
    ) -> Optional[datetime]:
        """Convert UTC nanoseconds to exchange local time."""
        tz_name = self.EXCHANGE_TIMEZONES.get(exchange_id.upper())
        if not tz_name:
            logger.warning("Unknown exchange timezone: %s", exchange_id)
            return None

        tz = pytz.timezone(tz_name)
        utc_dt = datetime.fromtimestamp(utc_ns / 1e9, tz=timezone.utc)
        return utc_dt.astimezone(tz)

    async def convert_to_utc(
        self, dt: datetime, tz_name: str = "UTC"
    ) -> int:
        """Convert a timezone-aware datetime to UTC nanoseconds."""
        if dt.tzinfo is None:
            tz = pytz.timezone(tz_name)
            dt = tz.localize(dt)
        utc_dt = dt.astimezone(timezone.utc)
        return int(utc_dt.timestamp() * 1e9)

    async def convert_to_timezone(
        self, utc_ns: int, tz_name: str
    ) -> Optional[datetime]:
        """Convert UTC nanoseconds to any timezone."""
        try:
            tz = pytz.timezone(tz_name)
            utc_dt = datetime.fromtimestamp(utc_ns / 1e9, tz=timezone.utc)
            return utc_dt.astimezone(tz)
        except pytz.UnknownTimeZoneError:
            logger.warning("Unknown timezone: %s", tz_name)
            return None

    async def get_exchange_timezone(self, exchange_id: str) -> Optional[str]:
        """Get the IANA timezone for an exchange."""
        return self.EXCHANGE_TIMEZONES.get(exchange_id.upper())

    async def register_exchange_timezone(self, exchange_id: str, tz_name: str) -> None:
        """Register a custom exchange timezone mapping."""
        try:
            pytz.timezone(tz_name)
            self.EXCHANGE_TIMEZONES[exchange_id.upper()] = tz_name
            logger.debug("Registered timezone %s for exchange %s", tz_name, exchange_id)
        except pytz.UnknownTimeZoneError:
            logger.error("Invalid timezone: %s", tz_name)

    async def is_trading_hours(
        self, utc_ns: int, exchange_id: str
    ) -> bool:
        """Check if the timestamp falls within exchange trading hours."""
        local_dt = await self.convert_to_exchange_time(utc_ns, exchange_id)
        if local_dt is None:
            return False

        # Basic check: weekdays only, 09:00-17:00 local
        if local_dt.weekday() >= 5:
            return False

        hour = local_dt.hour + local_dt.minute / 60.0
        return 9.0 <= hour < 17.0
