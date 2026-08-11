"""
Signal Dispatcher — Fan-out delivery of signals to downstream consumers.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Provides:
    - Registration of signal consumers
    - Batched dispatch with retry
    - Consumer health tracking
    - Delivery acknowledgement
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional

from services.strategy.signal.signal_engine import Signal, SignalBatch
from services.strategy.signal.signal_manager import SignalManager, ManagerEvent, ManagerEventType
from services.strategy.signal.signal_cache import SignalCache

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class ConsumerStatus(str, Enum):
    ACTIVE = "ACTIVE"
    DEGRADED = "DEGRADED"
    DISCONNECTED = "DISCONNECTED"


SignalConsumer = Callable[[List[Signal]], Coroutine[Any, Any, None]]


@dataclass
class ConsumerInfo:
    """Metadata for a registered signal consumer."""
    consumer_id: str
    name: str = ""
    consumer_type: str = ""  # "oms", "risk", "logging", "analytics", etc.
    handler: Optional[SignalConsumer] = None
    status: ConsumerStatus = ConsumerStatus.ACTIVE
    registered_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_delivery: Optional[datetime] = None
    delivery_count: int = 0
    failure_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Signal Dispatcher
# ---------------------------------------------------------------------------

class SignalDispatcher:
    """Fan-out dispatcher that delivers signals to all registered consumers.

    Features:
        - Concurrent delivery to all consumers
        - Per-consumer retry with backoff
        - Consumer health degradation tracking
        - Batch delivery support
    """

    MAX_RETRIES = 3
    RETRY_BASE_DELAY = 0.5  # seconds
    MAX_FAILURES_BEFORE_DEGRADE = 10

    def __init__(self, manager: SignalManager, cache: SignalCache):
        self.manager = manager
        self.cache = cache
        self._consumers: Dict[str, ConsumerInfo] = {}
        self._initialized = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def initialize(self) -> None:
        if self._initialized:
            return
        self.manager.subscribe(ManagerEventType.SIGNAL_PUBLISHED, self._on_signal_published)
        self._initialized = True
        logger.info("SignalDispatcher initialized")

    async def shutdown(self) -> None:
        self._consumers.clear()
        self._initialized = False
        logger.info("SignalDispatcher shut down")

    # ------------------------------------------------------------------
    # Consumer Management
    # ------------------------------------------------------------------

    def register_consumer(self, info: ConsumerInfo) -> None:
        """Register a downstream consumer for signal delivery."""
        self._consumers[info.consumer_id] = info
        logger.info("Registered consumer: %s (%s)", info.consumer_id, info.consumer_type)

    def unregister_consumer(self, consumer_id: str) -> bool:
        """Remove a consumer."""
        if consumer_id in self._consumers:
            del self._consumers[consumer_id]
            logger.info("Unregistered consumer: %s", consumer_id)
            return True
        return False

    def get_consumer(self, consumer_id: str) -> Optional[ConsumerInfo]:
        return self._consumers.get(consumer_id)

    def list_consumers(self, consumer_type: Optional[str] = None) -> List[ConsumerInfo]:
        if consumer_type:
            return [c for c in self._consumers.values() if c.consumer_type == consumer_type]
        return list(self._consumers.values())

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def dispatch(self, batch: SignalBatch) -> None:
        """Deliver a batch of signals to all registered consumers."""
        if not self._consumers:
            logger.debug("No consumers registered, skipping dispatch")
            return

        active_consumers = [
            c for c in self._consumers.values()
            if c.status != ConsumerStatus.DISCONNECTED and c.handler
        ]

        if not active_consumers:
            return

        signals = batch.signals
        tasks = []
        for consumer in active_consumers:
            tasks.append(self._deliver_to_consumer(consumer, signals))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        success_count = sum(1 for r in results if r is True)

        # Emit event
        await self.manager.emit(ManagerEvent(
            event_type=ManagerEventType.SIGNAL_PUBLISHED,
            source="SignalDispatcher",
            payload={
                "batch_id": batch.batch_id,
                "signal_count": len(signals),
                "consumer_count": len(active_consumers),
                "success_count": success_count,
            },
        ))

        logger.debug("Dispatched %d signals to %d/%d consumers",
                      len(signals), success_count, len(active_consumers))

    async def _deliver_to_consumer(self, consumer: ConsumerInfo, signals: List[Signal]) -> bool:
        """Deliver signals to a single consumer with retry logic."""
        if not consumer.handler:
            return False

        for attempt in range(self.MAX_RETRIES):
            try:
                await consumer.handler(signals)
                consumer.last_delivery = datetime.now(timezone.utc)
                consumer.delivery_count += 1
                # Reset failure count on success
                if consumer.failure_count > 0:
                    consumer.failure_count = 0
                    if consumer.status == ConsumerStatus.DEGRADED:
                        consumer.status = ConsumerStatus.ACTIVE
                return True
            except Exception:
                consumer.failure_count += 1
                logger.warning(
                    "Delivery to %s failed (attempt %d/%d): %s",
                    consumer.consumer_id, attempt + 1, self.MAX_RETRIES,
                    "will retry" if attempt < self.MAX_RETRIES - 1 else "giving up",
                )
                if attempt < self.MAX_RETRIES - 1:
                    delay = self.RETRY_BASE_DELAY * (2 ** attempt)
                    await asyncio.sleep(delay)

        # Mark degraded after repeated failures
        if consumer.failure_count >= self.MAX_FAILURES_BEFORE_DEGRADE:
            consumer.status = ConsumerStatus.DEGRADED
            logger.warning("Consumer %s marked as DEGRADED", consumer.consumer_id)

        return False

    # ------------------------------------------------------------------
    # Event Handler
    # ------------------------------------------------------------------

    async def _on_signal_published(self, event: ManagerEvent) -> None:
        """React to signal published events from the manager."""
        # This allows re-dispatch if needed
        pass

    # ------------------------------------------------------------------
    # Status
    # ------------------------------------------------------------------

    @property
    def consumer_count(self) -> int:
        return len(self._consumers)

    @property
    def active_consumer_count(self) -> int:
        return sum(1 for c in self._consumers.values() if c.status == ConsumerStatus.ACTIVE)

    @property
    def is_initialized(self) -> bool:
        return self._initialized
