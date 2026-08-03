"""
Log filters.

Provides a filter framework for
conditional log processing, enabling
level-based, sampling-based, and
strategy-based filtering of log records.
"""

from __future__ import annotations

import random
from typing import Any, Dict, Optional, Set

from .constants import LOG_LEVEL_NUMERIC
from .models import LogEntry


class LogFilter:
    """
    Base log filter.

    Subclasses implement the allow()
    method to determine whether a log
    record should be processed.

    Usage:
        filter = LevelFilter(min_level="WARNING")
        if filter.allow(record):
            # Process record
    """

    async def allow(
        self,
        record: LogEntry,
    ) -> bool:
        """
        Check if a record should be allowed.

        Args:
            record: LogEntry to check.

        Returns:
            True if record should be processed.
        """

        return True


class LevelFilter(LogFilter):
    """
    Level-based log filter.

    Filters log records by minimum level,
    allowing only records at or above
    the specified level.

    Usage:
        filter = LevelFilter(min_level="WARNING")
        # Only WARNING, ERROR, CRITICAL pass
    """

    def __init__(
        self,
        min_level: str = "DEBUG",
    ) -> None:
        """
        Initialize level filter.

        Args:
            min_level: Minimum log level to allow.
        """

        self._min_level = min_level.upper()
        self._min_numeric = LOG_LEVEL_NUMERIC.get(
            self._min_level, 0
        )

    async def allow(
        self,
        record: LogEntry,
    ) -> bool:
        """Check if record meets minimum level."""

        record_level = LOG_LEVEL_NUMERIC.get(
            record.level, 20
        )
        return record_level >= self._min_numeric


class SamplingFilter(LogFilter):
    """
    Sampling log filter.

    Allows only a fraction of log records
    to pass through, useful for high-volume
    log streams.

    Usage:
        filter = SamplingFilter(rate=0.1)  # 10% sampling
    """

    def __init__(
        self,
        rate: float = 1.0,
    ) -> None:
        """
        Initialize sampling filter.

        Args:
            rate: Sampling rate (0.0 to 1.0).
        """

        self._rate = max(0.0, min(1.0, rate))

    async def allow(
        self,
        record: LogEntry,
    ) -> bool:
        """Check if record passes sampling."""

        if self._rate >= 1.0:
            return True
        if self._rate <= 0.0:
            return False
        return random.random() < self._rate


class LoggerNameFilter(LogFilter):
    """
    Logger name filter.

    Filters log records by logger name,
    allowing only records from specified
    loggers.

    Usage:
        filter = LoggerNameFilter(allow={"strategy", "oms"})
        # Only records from "strategy" or "oms" loggers pass
    """

    def __init__(
        self,
        allow: Optional[Set[str]] = None,
        deny: Optional[Set[str]] = None,
    ) -> None:
        """
        Initialize logger name filter.

        Args:
            allow: Set of allowed logger names.
            deny: Set of denied logger names.
        """

        self._allow = allow or set()
        self._deny = deny or set()

    async def allow(
        self,
        record: LogEntry,
    ) -> bool:
        """Check if record is allowed by name."""

        if record.logger in self._deny:
            return False
        if self._allow and record.logger not in self._allow:
            return False
        return True


class CompositeFilter(LogFilter):
    """
    Composite log filter.

    Combines multiple filters with AND
    logic. A record must pass all filters
    to be allowed.

    Usage:
        composite = CompositeFilter([
            LevelFilter(min_level="INFO"),
            SamplingFilter(rate=0.5),
        ])
    """

    def __init__(
        self,
        filters: list = None,
    ) -> None:
        """
        Initialize composite filter.

        Args:
            filters: List of LogFilter instances.
        """

        self._filters = filters or []

    def add_filter(
        self,
        filter_obj: LogFilter,
    ) -> None:
        """
        Add a filter.

        Args:
            filter_obj: Filter to add.
        """

        self._filters.append(filter_obj)

    async def allow(
        self,
        record: LogEntry,
    ) -> bool:
        """Check if record passes all filters."""

        for f in self._filters:
            if not await f.allow(record):
                return False
        return True


class FieldFilter(LogFilter):
    """
    Field-based log filter.

    Filters log records by the presence
    or value of specific fields.

    Usage:
        filter = FieldFilter(
            required_fields={"symbol": "AAPL"}
        )
        # Only records with symbol=AAPL pass
    """

    def __init__(
        self,
        required_fields: Optional[Dict[str, Any]] = None,
        required_keys: Optional[Set[str]] = None,
    ) -> None:
        """
        Initialize field filter.

        Args:
            required_fields: Field name -> value pairs.
            required_keys: Field names that must exist.
        """

        self._required_fields = required_fields or {}
        self._required_keys = required_keys or set()

    async def allow(
        self,
        record: LogEntry,
    ) -> bool:
        """Check if record has required fields."""

        for key in self._required_keys:
            if key not in record.fields:
                return False

        for key, value in self._required_fields.items():
            if record.fields.get(key) != value:
                return False

        return True
