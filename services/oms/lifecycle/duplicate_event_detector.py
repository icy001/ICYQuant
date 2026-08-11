"""Duplicate Event Detector — Idempotent event processing.

Prevents duplicate events (ACK, fills, cancels, etc.) from causing
state corruption. Uses event ID-based deduplication with a configurable
TTL window.

Pipeline:
    Exchange Event → Duplicate Detection → Discard/Process

Key features:
- Event ID-based deduplication
- Configurable TTL for cache entries
- Efficient LRU-based eviction
- Thread-safe set operations
"""

from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class DuplicateCheckResult:
    """Result of duplicate event check."""
    event_id: str
    order_id: str
    is_duplicate: bool = False
    original_timestamp: Optional[datetime] = None
    current_timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "event_id": self.event_id,
            "order_id": self.order_id,
            "is_duplicate": self.is_duplicate,
            "original_timestamp": (
                self.original_timestamp.isoformat() if self.original_timestamp else None
            ),
            "current_timestamp": self.current_timestamp.isoformat(),
            "details": self.details,
        }


class DuplicateEventDetector:
    """Detects and prevents duplicate event processing.

    Uses an in-memory cache with TTL to track processed event IDs.
    When a duplicate is detected, the event is logged and discarded.

    Thread-safe for concurrent use.

    Usage::

        detector = DuplicateEventDetector(ttl_seconds=3600)
        result = detector.check(event_id, order_id)
        if result.is_duplicate:
            return  # discard
        # process event normally
    """

    def __init__(
        self,
        ttl_seconds: int = 3600,
        max_cache_size: int = 100_000,
    ) -> None:
        """Initialize duplicate event detector.

        Args:
            ttl_seconds: Time-to-live for cache entries in seconds
            max_cache_size: Maximum number of cached event IDs
        """
        self._ttl_seconds = ttl_seconds
        self._max_cache_size = max_cache_size
        self._cache: dict[str, float] = {}  # event_id -> expiry timestamp
        self._lock = threading.Lock()
        self._stats = {
            "total_checked": 0,
            "duplicates_found": 0,
            "cache_evictions": 0,
        }

    def check(self, event_id: str, order_id: str) -> DuplicateCheckResult:
        """Check if an event has been processed before.

        Args:
            event_id: Unique event identifier
            order_id: Associated order identifier

        Returns:
            DuplicateCheckResult with deduplication verdict
        """
        self._stats["total_checked"] += 1
        now = time.time()

        with self._lock:
            # Clean expired entries
            self._evict_expired()

            if event_id in self._cache:
                self._stats["duplicates_found"] += 1
                original_ts = datetime.fromtimestamp(
                    self._cache[event_id] - self._ttl_seconds, tz=timezone.utc
                )
                logger.warning(
                    f"Duplicate event detected: event_id={event_id}, order_id={order_id}"
                )
                return DuplicateCheckResult(
                    event_id=event_id,
                    order_id=order_id,
                    is_duplicate=True,
                    original_timestamp=original_ts,
                )

            # Register event
            self._cache[event_id] = now + self._ttl_seconds

            # Enforce cache size limit
            if len(self._cache) > self._max_cache_size:
                self._evict_oldest()
                self._stats["cache_evictions"] += 1

            logger.debug(f"Event registered: event_id={event_id}, order_id={order_id}")
            return DuplicateCheckResult(
                event_id=event_id,
                order_id=order_id,
                is_duplicate=False,
            )

    async def acheck(self, event_id: str, order_id: str) -> DuplicateCheckResult:
        """Async-compatible duplicate check.

        Args:
            event_id: Unique event identifier
            order_id: Associated order identifier

        Returns:
            DuplicateCheckResult with deduplication verdict
        """
        return self.check(event_id, order_id)

    def remove(self, event_id: str) -> None:
        """Remove an event from the cache.

        Args:
            event_id: Event to remove
        """
        with self._lock:
            self._cache.pop(event_id, None)

    def clear(self) -> None:
        """Clear all cached event IDs."""
        with self._lock:
            self._cache.clear()
            logger.info("Duplicate event cache cleared")

    def _evict_expired(self) -> None:
        """Remove expired cache entries."""
        now = time.time()
        expired = [eid for eid, expiry in self._cache.items() if expiry <= now]
        for eid in expired:
            del self._cache[eid]
        if expired:
            logger.debug(f"Evicted {len(expired)} expired duplicate entries")

    def _evict_oldest(self) -> None:
        """Remove oldest entries to stay within cache limit."""
        sorted_entries = sorted(self._cache.items(), key=lambda x: x[1])
        to_remove = len(self._cache) - self._max_cache_size + 1
        for eid, _ in sorted_entries[:to_remove]:
            del self._cache[eid]

    @property
    def cache_size(self) -> int:
        """Current cache size."""
        return len(self._cache)

    @property
    def stats(self) -> dict[str, int]:
        """Detector statistics."""
        with self._lock:
            return dict(self._stats)

    def to_dict(self) -> dict[str, Any]:
        """Serialize detector state."""
        with self._lock:
            return {
                "cache_size": len(self._cache),
                "ttl_seconds": self._ttl_seconds,
                "max_cache_size": self._max_cache_size,
                "stats": dict(self._stats),
            }
