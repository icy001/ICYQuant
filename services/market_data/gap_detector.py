"""
Gap Detector — detects gaps in market data sequences (missing ticks,
trades, orderbook updates) based on sequence numbers and timestamps.

Commit 16 Part 1.2
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class GapType(str, Enum):
    SEQUENCE = "sequence"         # Sequence number gap
    TIMESTAMP = "timestamp"       # Time gap (missing time period)
    ORDER_BOOK = "order_book"     # Missing order book levels
    VOLUME = "volume"             # Unexpected volume gap


@dataclass
class GapEvent:
    """A detected gap in market data."""

    gap_type: GapType = GapType.SEQUENCE
    instrument_id: str = ""
    exchange_id: str = ""
    start_seq: int = 0
    end_seq: int = 0
    missing_count: int = 0
    start_timestamp_ns: int = 0
    end_timestamp_ns: int = 0
    gap_duration_ns: int = 0
    detected_at_ns: int = 0
    severity: str = "warning"
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class GapDetectionConfig:
    """Configuration for gap detection."""

    max_sequence_gap: int = 5              # Max allowed sequence gap
    max_time_gap_ns: int = 5_000_000_000   # Max allowed time gap (5s)
    min_expected_interval_ns: int = 0      # Minimum expected tick interval
    alert_on_gap: bool = True
    track_per_instrument: bool = True


class GapDetector:
    """
    Detects gaps in market data sequences.

    Monitors:
    - Sequence number gaps (missing messages)
    - Time gaps (silence periods)
    - Order book level gaps
    - Volume discontinuities
    """

    def __init__(self, config: Optional[GapDetectionConfig] = None) -> None:
        self._config = config or GapDetectionConfig()
        self._last_seq: dict[str, int] = {}          # instrument_id → last_seq_num
        self._last_timestamp: dict[str, int] = {}     # instrument_id → last_ts_ns
        self._gaps: list[GapEvent] = []
        self._stats: dict[str, int] = {"total_gaps": 0, "total_missing": 0}

    async def initialize(self) -> None:
        logger.info("GapDetector initialized (max_seq_gap: %d, max_time_gap: %dns)",
                     self._config.max_sequence_gap, self._config.max_time_gap_ns)

    # ── Detection ──────────────────────────────────

    async def check_sequence(
        self,
        instrument_id: str,
        sequence_num: int,
        timestamp_ns: int = 0,
        exchange_id: str = "",
    ) -> Optional[GapEvent]:
        """Check for sequence number gaps."""

        if instrument_id not in self._last_seq:
            self._last_seq[instrument_id] = sequence_num
            self._last_timestamp[instrument_id] = timestamp_ns or self._now_ns()
            return None

        last_seq = self._last_seq[instrument_id]
        expected = last_seq + 1
        gap_size = sequence_num - expected

        self._last_seq[instrument_id] = sequence_num
        self._last_timestamp[instrument_id] = timestamp_ns or self._now_ns()

        if gap_size > self._config.max_sequence_gap:
            gap = GapEvent(
                gap_type=GapType.SEQUENCE,
                instrument_id=instrument_id,
                exchange_id=exchange_id,
                start_seq=last_seq,
                end_seq=sequence_num,
                missing_count=gap_size,
                start_timestamp_ns=timestamp_ns,
                end_timestamp_ns=timestamp_ns,
                detected_at_ns=self._now_ns(),
                severity="warning" if gap_size < 100 else "error",
            )
            self._gaps.append(gap)
            self._stats["total_gaps"] += 1
            self._stats["total_missing"] += gap_size

            if self._config.alert_on_gap:
                logger.warning("Gap detected: %s seq %d→%d (missing %d)",
                               instrument_id, last_seq, sequence_num, gap_size)

            return gap

        return None

    async def check_time_gap(
        self,
        instrument_id: str,
        timestamp_ns: int,
        exchange_id: str = "",
    ) -> Optional[GapEvent]:
        """Check for time gaps between consecutive events."""

        if instrument_id not in self._last_timestamp:
            self._last_timestamp[instrument_id] = timestamp_ns
            return None

        last_ts = self._last_timestamp[instrument_id]
        time_gap = timestamp_ns - last_ts
        self._last_timestamp[instrument_id] = timestamp_ns

        if time_gap > self._config.max_time_gap_ns:
            gap = GapEvent(
                gap_type=GapType.TIMESTAMP,
                instrument_id=instrument_id,
                exchange_id=exchange_id,
                start_timestamp_ns=last_ts,
                end_timestamp_ns=timestamp_ns,
                gap_duration_ns=time_gap,
                detected_at_ns=self._now_ns(),
                severity="warning" if time_gap < 30_000_000_000 else "error",
            )
            self._gaps.append(gap)
            self._stats["total_gaps"] += 1

            if self._config.alert_on_gap:
                logger.warning("Time gap: %s %.1fs without data",
                               instrument_id, time_gap / 1e9)

            return gap

        return None

    async def check_batch(
        self,
        records: list[dict[str, Any]],
    ) -> list[GapEvent]:
        """Check a batch of records for gaps."""
        gaps: list[GapEvent] = []
        for record in records:
            inst_id = record.get("instrument_id", record.get("symbol", ""))
            seq = record.get("sequence", record.get("seq_num", 0))
            ts = record.get("event_time", record.get("timestamp", 0))
            ex = record.get("exchange_id", "")

            if seq:
                gap = await self.check_sequence(inst_id, seq, ts, ex)
                if gap:
                    gaps.append(gap)
            elif ts:
                gap = await self.check_time_gap(inst_id, ts, ex)
                if gap:
                    gaps.append(gap)

        return gaps

    # ── Reporting ──────────────────────────────────

    async def get_recent_gaps(self, limit: int = 100) -> list[GapEvent]:
        """Get recent gap events."""
        return self._gaps[-limit:]

    async def get_gaps_for_instrument(self, instrument_id: str) -> list[GapEvent]:
        """Get all gaps for a specific instrument."""
        return [g for g in self._gaps if g.instrument_id == instrument_id]

    async def reset(self) -> None:
        """Reset detection state."""
        self._last_seq.clear()
        self._last_timestamp.clear()
        self._gaps.clear()
        self._stats = {"total_gaps": 0, "total_missing": 0}

    @property
    def stats(self) -> dict[str, int]:
        return dict(self._stats)

    @property
    def gap_count(self) -> int:
        return len(self._gaps)

    @staticmethod
    def _now_ns() -> int:
        return int(datetime.now(timezone.utc).timestamp() * 1e9)


# Type alias for __init__.py compatibility
GapRecord = GapEvent
