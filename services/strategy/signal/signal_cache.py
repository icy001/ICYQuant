"""
Signal Cache — In-memory signal store with TTL and fast lookup.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Provides:
    - O(1) signal lookup by ID
    - Indexed queries by strategy and instrument
    - Configurable TTL with lazy eviction
    - Active signal tracking
"""

from __future__ import annotations

import logging
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Dict, List, Optional, Set

from services.strategy.signal.signal_engine import Signal, SignalStatus

logger = logging.getLogger(__name__)


class SignalCache:
    """High-performance in-memory signal cache.

    Features:
        - OrderedDict-based LRU-like storage
        - Strategy and instrument indexes for fast filtering
        - TTL-based expiration (lazy eviction)
        - Max capacity enforcement
    """

    DEFAULT_MAX_SIZE = 10_000
    DEFAULT_TTL_SECONDS = 300.0  # 5 minutes

    def __init__(self, max_size: int = DEFAULT_MAX_SIZE, ttl_seconds: float = DEFAULT_TTL_SECONDS):
        self._max_size = max_size
        self._ttl_seconds = ttl_seconds
        self._signals: OrderedDict[str, Signal] = OrderedDict()
        self._index_strategy: Dict[str, Set[str]] = {}  # strategy_id → {signal_ids}
        self._index_instrument: Dict[str, Set[str]] = {}  # instrument → {signal_ids}
        self._index_status: Dict[str, Set[str]] = {}  # status → {signal_ids}

    # ------------------------------------------------------------------
    # CRUD
    # ------------------------------------------------------------------

    def put(self, signal: Signal) -> str:
        """Store a signal in the cache. Evicts oldest if at capacity."""
        self._evict_if_needed()
        signal_id = signal.signal_id

        self._signals[signal_id] = signal
        self._add_to_index(self._index_strategy, signal.strategy_id, signal_id)
        self._add_to_index(self._index_instrument, signal.instrument, signal_id)
        self._add_to_index(self._index_status, signal.status.value, signal_id)

        return signal_id

    def put_batch(self, signals: List[Signal]) -> List[str]:
        """Store multiple signals."""
        return [self.put(s) for s in signals]

    def get(self, signal_id: str) -> Optional[Signal]:
        """Retrieve a signal by ID. Returns None if expired or not found."""
        sig = self._signals.get(signal_id)
        if sig is None:
            return None
        if self._is_expired(sig):
            self._remove_signal(signal_id)
            return None
        return sig

    def update(self, signal_id: str, signal: Signal) -> bool:
        """Replace an existing signal."""
        if signal_id in self._signals:
            self._remove_signal(signal_id)
        self.put(signal)
        return True

    def remove(self, signal_id: str) -> bool:
        """Remove a signal from cache."""
        return self._remove_signal(signal_id)

    async def cancel(self, signal_id: str) -> bool:
        """Cancel an active signal by marking it CANCELLED."""
        sig = self._signals.get(signal_id)
        if sig and sig.status not in (SignalStatus.EXPIRED, SignalStatus.CANCELLED):
            sig.status = SignalStatus.CANCELLED
            self._add_to_index(self._index_status, SignalStatus.CANCELLED.value, signal_id)
            return True
        return False

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    async def get_active(self, strategy_id: Optional[str] = None) -> List[Signal]:
        """Get all active (non-terminal) signals, optionally filtered by strategy."""
        active = []
        for sig in list(self._signals.values()):
            if self._is_expired(sig):
                self._remove_signal(sig.signal_id)
                continue
            if sig.status in (SignalStatus.EXPIRED, SignalStatus.CANCELLED):
                continue
            if strategy_id and sig.strategy_id != strategy_id:
                continue
            active.append(sig)
        return active

    def get_by_strategy(self, strategy_id: str) -> List[Signal]:
        """Get all cached signals for a strategy."""
        ids = self._index_strategy.get(strategy_id, set())
        signals = []
        for sid in list(ids):
            sig = self._signals.get(sid)
            if sig and not self._is_expired(sig):
                signals.append(sig)
            elif sig is None:
                ids.discard(sid)
        return signals

    def get_by_instrument(self, instrument: str) -> List[Signal]:
        """Get all cached signals for an instrument."""
        ids = self._index_instrument.get(instrument, set())
        signals = []
        for sid in list(ids):
            sig = self._signals.get(sid)
            if sig and not self._is_expired(sig):
                signals.append(sig)
            elif sig is None:
                ids.discard(sid)
        return signals

    def get_by_status(self, status: SignalStatus) -> List[Signal]:
        """Get all signals with a given status."""
        ids = self._index_status.get(status.value, set())
        return [self._signals[sid] for sid in ids if sid in self._signals]

    # ------------------------------------------------------------------
    # Expiration
    # ------------------------------------------------------------------

    def expire_stale(self) -> List[str]:
        """Remove all expired signals. Returns list of expired IDs."""
        expired_ids = []
        for sig in list(self._signals.values()):
            if self._is_expired(sig):
                self._remove_signal(sig.signal_id)
                sig.status = SignalStatus.EXPIRED
                expired_ids.append(sig.signal_id)
        if expired_ids:
            logger.debug("Expired %d stale signals", len(expired_ids))
        return expired_ids

    def _is_expired(self, signal: Signal) -> bool:
        """Check if a signal has exceeded its TTL."""
        if signal.expiration:
            return datetime.now(timezone.utc) > signal.expiration
        elapsed = (datetime.now(timezone.utc) - signal.timestamp).total_seconds()
        return elapsed > self._ttl_seconds

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _add_to_index(self, index: Dict[str, Set[str]], key: str, signal_id: str) -> None:
        if key:
            index.setdefault(key, set()).add(signal_id)

    def _remove_from_index(self, index: Dict[str, Set[str]], key: str, signal_id: str) -> None:
        if key in index:
            index[key].discard(signal_id)
            if not index[key]:
                del index[key]

    def _remove_signal(self, signal_id: str) -> bool:
        sig = self._signals.pop(signal_id, None)
        if sig:
            self._remove_from_index(self._index_strategy, sig.strategy_id, signal_id)
            self._remove_from_index(self._index_instrument, sig.instrument, signal_id)
            self._remove_from_index(self._index_status, sig.status.value, signal_id)
            return True
        return False

    def _evict_if_needed(self) -> None:
        """Evict oldest entries if at capacity."""
        while len(self._signals) >= self._max_size:
            oldest_id, _ = self._signals.popitem(last=False)
            self._remove_signal(oldest_id)

    # ------------------------------------------------------------------
    # Stats
    # ------------------------------------------------------------------

    @property
    def size(self) -> int:
        return len(self._signals)

    @property
    def strategy_count(self) -> int:
        return len(self._index_strategy)

    @property
    def instrument_count(self) -> int:
        return len(self._index_instrument)

    def clear(self) -> None:
        self._signals.clear()
        self._index_strategy.clear()
        self._index_instrument.clear()
        self._index_status.clear()
