"""
Timestamp Normalizer — converts all timestamps to canonical nanosecond
UTC format.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Union

logger = logging.getLogger(__name__)


class TimestampUnit(str, Enum):
    SECONDS = "seconds"
    MILLISECONDS = "milliseconds"
    MICROSECONDS = "microseconds"
    NANOSECONDS = "nanoseconds"


class TimestampNormalizer:
    """
    Normalizes timestamps from any format into canonical nanosecond UTC.

    Detects and converts:
    - Unix seconds (10-digit)
    - Unix milliseconds (13-digit)
    - Unix microseconds (16-digit)
    - Unix nanoseconds (19-digit)
    - ISO 8601 strings
    - datetime objects
    - Exchange-specific formats (e.g., "2024-01-15T09:30:00.123456Z")
    """

    NS_PER_SECOND = 1_000_000_000
    NS_PER_MS = 1_000_000
    NS_PER_US = 1_000

    async def normalize(
        self,
        value: Union[int, float, str, datetime, None],
        unit: Optional[TimestampUnit] = None,
    ) -> int:
        """Convert any timestamp to nanoseconds UTC."""

        if value is None:
            return 0

        if isinstance(value, datetime):
            return self._datetime_to_ns(value)

        if isinstance(value, (int, float)):
            if unit:
                return self._unit_to_ns(int(value), unit)
            return self._auto_detect_ns(value)

        if isinstance(value, str):
            return self._parse_string(value)

        return 0

    def normalize_batch(
        self,
        values: list[Union[int, float, str, datetime, None]],
        unit: Optional[TimestampUnit] = None,
    ) -> list[int]:
        """Normalize a batch of timestamps."""
        import asyncio
        return [asyncio.get_event_loop().run_until_complete(self.normalize(v, unit)) for v in values]

    # ── Internal ───────────────────────────────────

    def _auto_detect_ns(self, value: Union[int, float]) -> int:
        """Auto-detect timestamp unit from magnitude."""
        val = int(value)
        if val > 1e18:  # nanoseconds
            return val
        if val > 1e15:  # microseconds
            return val * self.NS_PER_US
        if val > 1e12:  # milliseconds
            return val * self.NS_PER_MS
        # Assume seconds
        return val * self.NS_PER_SECOND

    @staticmethod
    def _unit_to_ns(value: int, unit: TimestampUnit) -> int:
        multipliers = {
            TimestampUnit.SECONDS: 1_000_000_000,
            TimestampUnit.MILLISECONDS: 1_000_000,
            TimestampUnit.MICROSECONDS: 1_000,
            TimestampUnit.NANOSECONDS: 1,
        }
        return value * multipliers.get(unit, 1)

    @staticmethod
    def _datetime_to_ns(dt: datetime) -> int:
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1e9)

    @staticmethod
    def _parse_string(value: str) -> int:
        """Parse ISO 8601 or numeric string."""
        value = value.strip()

        # Try numeric first
        try:
            num = float(value)
            return int(num * 1e9) if num < 1e11 else int(num)
        except ValueError:
            pass

        # ISO 8601 parsing
        for fmt in [
            "%Y-%m-%dT%H:%M:%S.%fZ",
            "%Y-%m-%dT%H:%M:%SZ",
            "%Y-%m-%dT%H:%M:%S.%f%z",
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%d %H:%M:%S.%f",
            "%Y-%m-%d %H:%M:%S",
            "%Y%m%dT%H:%M:%S.%f",
            "%Y%m%dT%H:%M:%S",
        ]:
            try:
                dt = datetime.strptime(value, fmt)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return int(dt.timestamp() * 1e9)
            except ValueError:
                continue

        logger.warning("Could not parse timestamp: %s", value)
        return 0

    @staticmethod
    def ns_to_datetime(ns: int) -> datetime:
        """Convert nanoseconds to datetime."""
        return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc)

    @staticmethod
    def now_ns() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1e9)
