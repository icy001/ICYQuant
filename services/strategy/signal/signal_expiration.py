"""
Signal Expiration — Time-based and event-based signal expiration management.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Provides:
    - TTL-based automatic expiration
    - Event-driven expiration (market close, session end, etc.)
    - Batch expiration with callback hooks
    - Expiration reason tracking
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Callable, Dict, List, Optional

from services.strategy.signal.signal_engine import Signal, SignalStatus
from services.strategy.signal.signal_cache import SignalCache

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ExpirationReason(str, Enum):
    """Reasons for signal expiration."""
    TTL_EXCEEDED = "ttl_exceeded"
    MARKET_CLOSE = "market_close"
    SESSION_END = "session_end"
    STRATEGY_STOP = "strategy_stop"
    MANUAL = "manual"
    REPLACED = "replaced"


@dataclass
class ExpirationConfig:
    """Configuration for signal expiration."""
    default_ttl_seconds: float = 300.0  # 5 minutes
    expire_on_market_close: bool = True
    expire_on_session_end: bool = True
    check_interval_seconds: float = 10.0
    max_expiry_batch: int = 1000


@dataclass
class ExpirationEvent:
    """Record of a signal expiration."""
    signal_id: str
    reason: ExpirationReason
    expired_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    strategy_id: str = ""
    instrument: str = ""


# ---------------------------------------------------------------------------
# Signal Expiration
# ---------------------------------------------------------------------------

class SignalExpiration:
    """Manages signal expiration lifecycle.

    Can be configured with TTL policies and event-driven expiration triggers.
    Runs a background task to periodically check for stale signals.
    """

    def __init__(
        self,
        cache: SignalCache,
        config: Optional[ExpirationConfig] = None,
    ):
        self.cache = cache
        self.config = config or ExpirationConfig()
        self._callbacks: List[Callable[[List[ExpirationEvent]], None]] = []
        self._expiration_history: List[ExpirationEvent] = []
        self._task: Optional[asyncio.Task] = None
        self._running = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._running:
            return
        self._running = True
        self._task = asyncio.create_task(self._expiration_loop())
        logger.info("SignalExpiration initialized (ttl=%.0fs, interval=%.0fs)",
                     self.config.default_ttl_seconds, self.config.check_interval_seconds)

    async def shutdown(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("SignalExpiration shut down")

    # ------------------------------------------------------------------
    # Expiration Operations
    # ------------------------------------------------------------------

    async def expire(self) -> List[str]:
        """Check and expire all stale signals. Returns expired signal IDs."""
        # TTL-based
        expired_ids = self.cache.expire_stale()

        events = []
        for sid in expired_ids:
            sig = self.cache.get(sid)  # Will be None after removal
            events.append(ExpirationEvent(
                signal_id=sid,
                reason=ExpirationReason.TTL_EXCEEDED,
                strategy_id=sig.strategy_id if sig else "",
                instrument=sig.instrument if sig else "",
            ))

        if events:
            self._expiration_history.extend(events)
            # Trim history
            if len(self._expiration_history) > 10000:
                self._expiration_history = self._expiration_history[-5000:]
            # Fire callbacks
            for cb in self._callbacks:
                try:
                    cb(events)
                except Exception:
                    logger.exception("Expiration callback error")

        return expired_ids

    async def expire_strategy(self, strategy_id: str) -> int:
        """Expire all signals for a given strategy."""
        signals = self.cache.get_by_strategy(strategy_id)
        count = 0
        for sig in signals:
            sig.status = SignalStatus.EXPIRED
            count += 1
            self._expiration_history.append(ExpirationEvent(
                signal_id=sig.signal_id,
                reason=ExpirationReason.STRATEGY_STOP,
                strategy_id=strategy_id,
                instrument=sig.instrument,
            ))
        return count

    async def expire_instrument(self, instrument: str) -> int:
        """Expire all signals for a given instrument."""
        signals = self.cache.get_by_instrument(instrument)
        count = 0
        for sig in signals:
            sig.status = SignalStatus.EXPIRED
            count += 1
            self._expiration_history.append(ExpirationEvent(
                signal_id=sig.signal_id,
                reason=ExpirationReason.MARKET_CLOSE,
                instrument=instrument,
                strategy_id=sig.strategy_id,
            ))
        return count

    async def expire_market_close(self) -> int:
        """Expire signals that should not persist past market close."""
        if not self.config.expire_on_market_close:
            return 0
        active = await self.cache.get_active()
        count = 0
        for sig in active:
            if sig.metadata.get("expire_on_market_close", True):
                sig.status = SignalStatus.EXPIRED
                count += 1
        return count

    # ------------------------------------------------------------------
    # Callbacks
    # ------------------------------------------------------------------

    def on_expiration(self, callback: Callable[[List[ExpirationEvent]], None]) -> None:
        """Register a callback for expiration events."""
        self._callbacks.append(callback)

    # ------------------------------------------------------------------
    # Background Loop
    # ------------------------------------------------------------------

    async def _expiration_loop(self) -> None:
        """Periodic expiration check."""
        while self._running:
            try:
                await asyncio.sleep(self.config.check_interval_seconds)
                await self.expire()
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Expiration loop error")

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def get_expiration_history(self, limit: int = 100) -> List[ExpirationEvent]:
        return self._expiration_history[-limit:]

    @property
    def total_expired(self) -> int:
        return len(self._expiration_history)
