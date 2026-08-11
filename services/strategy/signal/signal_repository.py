"""
Signal Repository — Signal persistence and query layer.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Provides:
    - Persistent storage of signal history
    - Query by strategy, instrument, time range, direction
    - Bulk insert and pagination
    - Signal statistics aggregation
"""

from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from services.strategy.signal.signal_engine import Signal, SignalDirection, SignalStatus

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Query Models
# ---------------------------------------------------------------------------

class SortOrder(str, Enum):
    ASC = "ASC"
    DESC = "DESC"


@dataclass
class SignalQuery:
    """Flexible query for signal history."""
    strategy_id: Optional[str] = None
    instrument: Optional[str] = None
    direction: Optional[SignalDirection] = None
    status: Optional[SignalStatus] = None
    min_confidence: Optional[float] = None
    from_time: Optional[datetime] = None
    to_time: Optional[datetime] = None
    sort_by: str = "timestamp"
    sort_order: SortOrder = SortOrder.DESC
    limit: int = 100
    offset: int = 0
    tags: Optional[List[str]] = None


@dataclass
class SignalStats:
    """Aggregated statistics for signals."""
    total_count: int = 0
    by_direction: Dict[str, int] = field(default_factory=dict)
    by_status: Dict[str, int] = field(default_factory=dict)
    avg_confidence: float = 0.0
    max_confidence: float = 0.0
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None


# ---------------------------------------------------------------------------
# Signal Repository
# ---------------------------------------------------------------------------

class SignalRepository:
    """Persistent storage for signal history.

    In production, this would be backed by a database. For now, uses an
    in-memory ordered store with a configurable maximum capacity.
    """

    DEFAULT_MAX_CAPACITY = 100_000

    def __init__(self, max_capacity: int = DEFAULT_MAX_CAPACITY):
        self._max_capacity = max_capacity
        self._signals: OrderedDict[str, Signal] = OrderedDict()
        self._index_strategy: Dict[str, List[str]] = {}  # strategy_id → [signal_ids]
        self._index_instrument: Dict[str, List[str]] = {}  # instrument → [signal_ids]
        self._initialized = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return
        self._initialized = True
        logger.info("SignalRepository initialized (capacity=%d)", self._max_capacity)

    async def shutdown(self) -> None:
        self._signals.clear()
        self._index_strategy.clear()
        self._index_instrument.clear()
        self._initialized = False
        logger.info("SignalRepository shut down")

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    async def save(self, signal: Signal) -> str:
        """Persist a signal. Returns the signal ID."""
        self._evict_if_needed()
        self._signals[signal.signal_id] = signal

        # Update indexes
        self._index_strategy.setdefault(signal.strategy_id, []).append(signal.signal_id)
        self._index_instrument.setdefault(signal.instrument, []).append(signal.signal_id)

        return signal.signal_id

    async def save_batch(self, signals: List[Signal]) -> List[str]:
        """Persist multiple signals."""
        ids = []
        for sig in signals:
            ids.append(await self.save(sig))
        return ids

    async def get(self, signal_id: str) -> Optional[Signal]:
        """Retrieve a signal by ID."""
        return self._signals.get(signal_id)

    async def update_status(self, signal_id: str, status: SignalStatus) -> bool:
        """Update a signal's status."""
        sig = self._signals.get(signal_id)
        if sig:
            sig.status = status
            return True
        return False

    async def delete(self, signal_id: str) -> bool:
        """Remove a signal from the repository."""
        sig = self._signals.pop(signal_id, None)
        if sig:
            # Clean indexes
            if sig.strategy_id in self._index_strategy:
                self._index_strategy[sig.strategy_id] = [
                    sid for sid in self._index_strategy[sig.strategy_id] if sid != signal_id
                ]
            if sig.instrument in self._index_instrument:
                self._index_instrument[sig.instrument] = [
                    sid for sid in self._index_instrument[sig.instrument] if sid != signal_id
                ]
            return True
        return False

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    async def query(self, q: SignalQuery) -> List[Signal]:
        """Query signals with flexible filters."""
        results = []

        for sig in self._signals.values():
            if q.strategy_id and sig.strategy_id != q.strategy_id:
                continue
            if q.instrument and sig.instrument != q.instrument:
                continue
            if q.direction and sig.direction != q.direction:
                continue
            if q.status and sig.status != q.status:
                continue
            if q.min_confidence is not None and sig.confidence < q.min_confidence:
                continue
            if q.from_time and sig.timestamp < q.from_time:
                continue
            if q.to_time and sig.timestamp > q.to_time:
                continue
            if q.tags:
                if not any(t in sig.tags for t in q.tags):
                    continue
            results.append(sig)

        # Sort
        reverse = q.sort_order == SortOrder.DESC
        results.sort(key=lambda s: getattr(s, q.sort_by, s.timestamp), reverse=reverse)

        # Paginate
        return results[q.offset: q.offset + q.limit]

    async def get_by_strategy(self, strategy_id: str, limit: int = 100) -> List[Signal]:
        """Get recent signals for a strategy."""
        ids = self._index_strategy.get(strategy_id, [])
        return [self._signals[sid] for sid in reversed(ids[-limit:]) if sid in self._signals]

    async def get_by_instrument(self, instrument: str, limit: int = 100) -> List[Signal]:
        """Get recent signals for an instrument."""
        ids = self._index_instrument.get(instrument, [])
        return [self._signals[sid] for sid in reversed(ids[-limit:]) if sid in self._signals]

    # ------------------------------------------------------------------
    # Statistics
    # ------------------------------------------------------------------

    async def get_stats(self, from_time: Optional[datetime] = None,
                        to_time: Optional[datetime] = None) -> SignalStats:
        """Compute aggregate statistics for signals in a time range."""
        stats = SignalStats()
        signals = list(self._signals.values())

        if from_time:
            signals = [s for s in signals if s.timestamp >= from_time]
        if to_time:
            signals = [s for s in signals if s.timestamp <= to_time]

        if not signals:
            return stats

        stats.total_count = len(signals)
        stats.period_start = min(s.timestamp for s in signals)
        stats.period_end = max(s.timestamp for s in signals)

        confidences = []
        for sig in signals:
            stats.by_direction[sig.direction.value] = stats.by_direction.get(sig.direction.value, 0) + 1
            stats.by_status[sig.status.value] = stats.by_status.get(sig.status.value, 0) + 1
            confidences.append(sig.confidence)

        stats.avg_confidence = sum(confidences) / len(confidences) if confidences else 0.0
        stats.max_confidence = max(confidences) if confidences else 0.0

        return stats

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _evict_if_needed(self) -> None:
        """Evict oldest signals if at capacity."""
        while len(self._signals) >= self._max_capacity:
            oldest_id, oldest_sig = self._signals.popitem(last=False)
            # Clean indexes
            if oldest_sig.strategy_id in self._index_strategy:
                self._index_strategy[oldest_sig.strategy_id] = [
                    sid for sid in self._index_strategy[oldest_sig.strategy_id] if sid != oldest_id
                ]
            if oldest_sig.instrument in self._index_instrument:
                self._index_instrument[oldest_sig.instrument] = [
                    sid for sid in self._index_instrument[oldest_sig.instrument] if sid != oldest_id
                ]

    @property
    def count(self) -> int:
        return len(self._signals)

    @property
    def is_initialized(self) -> bool:
        return self._initialized
