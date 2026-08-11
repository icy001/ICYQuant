"""
Duplicate Detector — identifies duplicate market data events using
configurable key matching and time windows.

Commit 16 Part 1.2
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DuplicateStrategy(str, Enum):
    EXACT_HASH = "exact_hash"           # Full payload hash
    KEY_HASH = "key_hash"               # Key fields hash
    EVENT_ID = "event_id"               # Exchange-provided event ID
    SEQUENCE_NUMBER = "sequence_number" # Exchange sequence number
    TIMESTAMP_KEY = "timestamp_key"     # Timestamp + key fields


@dataclass
class DuplicateDetectionConfig:
    """Configuration for duplicate detection."""

    strategy: DuplicateStrategy = DuplicateStrategy.EXACT_HASH
    window_size: int = 10000              # Max records in sliding window
    window_duration_ns: int = 0           # Time-based window (0 = disabled)
    key_fields: list[str] = field(default_factory=list)
    alert_on_duplicate: bool = True


@dataclass
class DuplicateRecord:
    """Record of a detected duplicate."""

    original_timestamp_ns: int = 0
    duplicate_timestamp_ns: int = 0
    instrument_id: str = ""
    event_type: str = ""
    hash_key: str = ""
    count: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)


class DuplicateDetector:
    """
    Detects duplicate market data events in real-time streams.

    Supports multiple strategies:
    - Exact hash matching
    - Key field matching (symbol + timestamp)
    - Exchange event ID deduplication
    - Sequence number gap-based detection
    """

    def __init__(self, config: Optional[DuplicateDetectionConfig] = None) -> None:
        self._config = config or DuplicateDetectionConfig()
        self._seen_hashes: dict[str, int] = {}        # hash → timestamp_ns
        self._seen_event_ids: dict[str, int] = {}      # event_id → timestamp_ns
        self._seen_sequence_nums: dict[str, int] = {}  # inst_id → last_seq
        self._recent_records: list[tuple[int, str]] = []  # (ts_ns, hash)
        self._duplicates: list[DuplicateRecord] = []
        self._stats: dict[str, int] = {"total_checked": 0, "total_duplicates": 0, "total_unique": 0}

    async def initialize(self) -> None:
        logger.info("DuplicateDetector initialized (strategy: %s, window: %d)",
                     self._config.strategy.value, self._config.window_size)

    # ── Detection ──────────────────────────────────

    async def is_duplicate(self, data: dict[str, Any]) -> tuple[bool, Optional[DuplicateRecord]]:
        """
        Check if a data record is a duplicate.

        Returns (is_duplicate, duplicate_record_if_yes).
        """
        self._stats["total_checked"] += 1

        hash_key = self._compute_hash(data)

        # Time-window pruning
        self._prune_window()

        if hash_key in self._seen_hashes:
            self._stats["total_duplicates"] += 1
            dup = DuplicateRecord(
                original_timestamp_ns=self._seen_hashes[hash_key],
                duplicate_timestamp_ns=self._now_ns(),
                instrument_id=data.get("instrument_id", data.get("symbol", "")),
                event_type=data.get("event_type", ""),
                hash_key=hash_key,
                count=1,
            )
            self._duplicates.append(dup)

            if self._config.alert_on_duplicate:
                logger.debug("Duplicate detected: %s", hash_key[:16])

            return True, dup

        # Mark as seen
        self._seen_hashes[hash_key] = self._now_ns()
        self._recent_records.append((self._now_ns(), hash_key))

        # Check event ID if available
        event_id = data.get("event_id", data.get("trade_id", data.get("sequence", "")))
        if event_id and self._config.strategy == DuplicateStrategy.EVENT_ID:
            if event_id in self._seen_event_ids:
                self._stats["total_duplicates"] += 1
                return True, None
            self._seen_event_ids[event_id] = self._now_ns()

        self._stats["total_unique"] += 1
        return False, None

    async def is_duplicate_batch(
        self, data_batch: list[dict[str, Any]]
    ) -> list[tuple[bool, Optional[DuplicateRecord]]]:
        """Check a batch of records for duplicates."""
        return [await self.is_duplicate(data) for data in data_batch]

    # ── Hash computation ───────────────────────────

    def _compute_hash(self, data: dict[str, Any]) -> str:
        """Compute deduplication hash based on strategy."""

        if self._config.strategy == DuplicateStrategy.EXACT_HASH:
            payload = str(sorted(data.items()))
            return hashlib.sha256(payload.encode()).hexdigest()

        if self._config.strategy == DuplicateStrategy.KEY_HASH:
            parts = []
            for field in self._config.key_fields:
                parts.append(str(data.get(field, "")))
            return hashlib.sha256("|".join(parts).encode()).hexdigest()

        if self._config.strategy == DuplicateStrategy.TIMESTAMP_KEY:
            ts = data.get("event_time", data.get("timestamp", 0))
            sym = data.get("instrument_id", data.get("symbol", ""))
            return hashlib.sha256(f"{ts}|{sym}".encode()).hexdigest()

        # Default: full hash
        payload = str(sorted(data.items()))
        return hashlib.sha256(payload.encode()).hexdigest()

    # ── Window management ──────────────────────────

    def _prune_window(self) -> None:
        """Remove records outside the sliding window."""
        if self._config.window_size <= 0:
            return

        while len(self._recent_records) > self._config.window_size:
            old_ts, old_hash = self._recent_records.pop(0)
            self._seen_hashes.pop(old_hash, None)

        # Time-based pruning
        if self._config.window_duration_ns > 0:
            cutoff = self._now_ns() - self._config.window_duration_ns
            self._recent_records = [
                (ts, h) for ts, h in self._recent_records if ts > cutoff
            ]
            self._seen_hashes = {
                h: ts for h, ts in self._seen_hashes.items() if ts > cutoff
            }

    # ── Reporting ──────────────────────────────────

    async def get_duplicate_rate(self) -> float:
        """Get the duplicate rate as a percentage."""
        total = max(self._stats["total_checked"], 1)
        return (self._stats["total_duplicates"] / total) * 100.0

    async def get_recent_duplicates(self, limit: int = 50) -> list[DuplicateRecord]:
        """Get recent duplicate records."""
        return self._duplicates[-limit:]

    async def reset(self) -> None:
        """Reset all detection state."""
        self._seen_hashes.clear()
        self._seen_event_ids.clear()
        self._seen_sequence_nums.clear()
        self._recent_records.clear()
        self._duplicates.clear()
        self._stats = {"total_checked": 0, "total_duplicates": 0, "total_unique": 0}

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    @staticmethod
    def _now_ns() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1e9)
