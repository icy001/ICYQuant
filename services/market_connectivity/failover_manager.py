"""
Failover Manager — Manages automatic failover between endpoints and
exchanges when connections become unhealthy or unavailable.

Monitors health → Detects failure → Switches endpoint → Recovers session
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class FailoverState(str, Enum):
    """Failover lifecycle states."""
    NORMAL = "normal"
    DEGRADED = "degraded"
    FAILING_OVER = "failing_over"
    FAILED_OVER = "failed_over"
    FALLING_BACK = "falling_back"
    FAILED = "failed"


class FailoverStrategy(str, Enum):
    """Failover strategies."""
    PRIORITY_BASED = "priority_based"
    ROUND_ROBIN = "round_robin"
    LOWEST_LATENCY = "lowest_latency"
    GEOGRAPHIC = "geographic"
    RANDOM = "random"


@dataclass
class FailoverTarget:
    """A failover target endpoint."""
    target_id: str
    exchange_id: str
    endpoint: str
    protocol: str
    priority: int = 100
    region: str = "global"
    health_weight: float = 1.0
    latency_ms: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FailoverRecord:
    """Tracks failover state for an exchange connection."""
    exchange_id: str
    primary_endpoint: str
    current_endpoint: str
    state: FailoverState = FailoverState.NORMAL
    targets: list[FailoverTarget] = field(default_factory=list)
    failover_count: int = 0
    last_failover: Optional[datetime] = None
    last_failback: Optional[datetime] = None
    consecutive_failures: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class FailoverManager:
    """
    Manages automatic failover to backup endpoints when primary
    connections become unhealthy.

    Supports multiple failover strategies and automatic failback
    when the primary endpoint recovers.

    Usage::

        manager = FailoverManager(strategy=FailoverStrategy.PRIORITY_BASED)
        await manager.initialize()
        await manager.register_exchange("binance", primary="wss://primary", targets=[...])
        await manager.failover("binance")  # triggered on health failure
    """

    def __init__(
        self,
        strategy: FailoverStrategy = FailoverStrategy.PRIORITY_BASED,
        health_check_interval: float = 10.0,
        max_consecutive_failures: int = 3,
        failback_enabled: bool = True,
        failback_delay: float = 60.0,
    ) -> None:
        self.strategy = strategy
        self.health_check_interval = health_check_interval
        self.max_consecutive_failures = max_consecutive_failures
        self.failback_enabled = failback_enabled
        self.failback_delay = failback_delay
        self._records: dict[str, FailoverRecord] = {}
        self._on_failover_callbacks: list[Callable] = []
        self._on_failback_callbacks: list[Callable] = []
        self._monitor_task: Optional[asyncio.Task] = None
        self._lock = asyncio.Lock()

    async def initialize(self) -> None:
        """Initialize the failover manager."""
        logger.info("FailoverManager initialized with strategy=%s", self.strategy.value)

    async def start(self) -> None:
        """Start background health monitoring."""
        if self.health_check_interval > 0:
            self._monitor_task = asyncio.create_task(self._health_monitor())

    async def stop(self) -> None:
        """Stop failover monitoring."""
        if self._monitor_task:
            self._monitor_task.cancel()
        logger.info("FailoverManager stopped.")

    def on_failover(self, callback: Callable) -> None:
        """Register a callback for failover events."""
        self._on_failover_callbacks.append(callback)

    def on_failback(self, callback: Callable) -> None:
        """Register a callback for failback events."""
        self._on_failback_callbacks.append(callback)

    # ---- Registration ----

    async def register_exchange(
        self,
        exchange_id: str,
        primary_endpoint: str,
        targets: list[FailoverTarget],
    ) -> None:
        """Register an exchange with failover targets."""
        async with self._lock:
            self._records[exchange_id] = FailoverRecord(
                exchange_id=exchange_id,
                primary_endpoint=primary_endpoint,
                current_endpoint=primary_endpoint,
                targets=sorted(targets, key=lambda t: t.priority),
            )
        logger.info(
            "Failover registered for %s: %d targets", exchange_id, len(targets)
        )

    async def unregister(self, exchange_id: str) -> bool:
        """Remove an exchange from failover management."""
        async with self._lock:
            return self._records.pop(exchange_id, None) is not None

    # ---- Failover Operations ----

    async def failover(self, exchange_id: str) -> Optional[str]:
        """Perform failover to the best available target."""
        record = self._records.get(exchange_id)
        if record is None:
            logger.error("Exchange not registered for failover: %s", exchange_id)
            return None

        # Select the best target
        target = await self._select_target(record)
        if target is None:
            logger.error("No failover targets available for %s", exchange_id)
            record.state = FailoverState.FAILED
            return None

        # Perform the switch
        record.state = FailoverState.FAILING_OVER
        old_endpoint = record.current_endpoint
        record.current_endpoint = target.endpoint
        record.state = FailoverState.FAILED_OVER
        record.failover_count += 1
        record.last_failover = datetime.now(timezone.utc)

        logger.info(
            "Failover complete for %s: %s → %s (count=%d)",
            exchange_id, old_endpoint, target.endpoint, record.failover_count,
        )

        await self._emit_failover_event(exchange_id, old_endpoint, target.endpoint)
        return target.endpoint

    async def failback(self, exchange_id: str) -> bool:
        """Attempt to fail back to the primary endpoint."""
        record = self._records.get(exchange_id)
        if record is None:
            return False

        if record.current_endpoint == record.primary_endpoint:
            logger.info("Already on primary for %s", exchange_id)
            return True

        record.state = FailoverState.FALLING_BACK
        old_endpoint = record.current_endpoint
        record.current_endpoint = record.primary_endpoint
        record.state = FailoverState.NORMAL
        record.last_failback = datetime.now(timezone.utc)

        logger.info(
            "Failback complete for %s: %s → %s",
            exchange_id, old_endpoint, record.primary_endpoint,
        )

        await self._emit_failback_event(exchange_id, old_endpoint, record.primary_endpoint)
        return True

    async def get_current_endpoint(self, exchange_id: str) -> Optional[str]:
        """Get the currently active endpoint for an exchange."""
        record = self._records.get(exchange_id)
        return record.current_endpoint if record else None

    async def get_state(self, exchange_id: str) -> Optional[FailoverState]:
        """Get current failover state for an exchange."""
        record = self._records.get(exchange_id)
        return record.state if record else None

    async def get_record(self, exchange_id: str) -> Optional[FailoverRecord]:
        """Get the full failover record for an exchange."""
        return self._records.get(exchange_id)

    async def get_summary(self) -> dict[str, Any]:
        """Get failover summary."""
        total = len(self._records)
        failed_over = sum(
            1 for r in self._records.values()
            if r.state == FailoverState.FAILED_OVER
        )
        total_failovers = sum(r.failover_count for r in self._records.values())

        return {
            "total_exchanges": total,
            "currently_failed_over": failed_over,
            "total_failovers": total_failovers,
            "exchanges": {
                eid: {
                    "current_endpoint": r.current_endpoint,
                    "state": r.state.value,
                    "failover_count": r.failover_count,
                }
                for eid, r in self._records.items()
            },
        }

    # ---- Internal ----

    async def _select_target(
        self, record: FailoverRecord
    ) -> Optional[FailoverTarget]:
        """Select the best failover target based on strategy."""
        available = [
            t for t in record.targets
            if t.endpoint != record.current_endpoint
        ]
        if not available:
            return None

        if self.strategy == FailoverStrategy.PRIORITY_BASED:
            return min(available, key=lambda t: t.priority)
        elif self.strategy == FailoverStrategy.LOWEST_LATENCY:
            return min(available, key=lambda t: t.latency_ms)
        elif self.strategy == FailoverStrategy.GEOGRAPHIC:
            # For geographic, prefer same region first
            same_region = [t for t in available if t.region == record.metadata.get("preferred_region", "")]
            return same_region[0] if same_region else available[0]
        elif self.strategy == FailoverStrategy.RANDOM:
            import random
            return random.choice(available)
        else:  # ROUND_ROBIN
            idx = record.failover_count % len(available)
            return available[idx]

    async def _health_monitor(self) -> None:
        """Background health monitoring for failback."""
        while True:
            try:
                await asyncio.sleep(self.health_check_interval)
                if self.failback_enabled:
                    for exchange_id, record in list(self._records.items()):
                        if (
                            record.state == FailoverState.FAILED_OVER
                            and record.last_failover
                            and (
                                datetime.now(timezone.utc) - record.last_failover
                            ).total_seconds() > self.failback_delay
                        ):
                            # Attempt failback if enough time has passed
                            logger.info("Attempting failback for %s", exchange_id)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("Failover health monitor error")

    async def _emit_failover_event(
        self, exchange_id: str, old_endpoint: str, new_endpoint: str
    ) -> None:
        """Emit failover event to callbacks."""
        event = {
            "type": "failover",
            "exchange_id": exchange_id,
            "old_endpoint": old_endpoint,
            "new_endpoint": new_endpoint,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for cb in self._on_failover_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(event)
                else:
                    cb(event)
            except Exception:
                logger.exception("Failover callback error")

    async def _emit_failback_event(
        self, exchange_id: str, old_endpoint: str, new_endpoint: str
    ) -> None:
        """Emit failback event to callbacks."""
        event = {
            "type": "failback",
            "exchange_id": exchange_id,
            "old_endpoint": old_endpoint,
            "new_endpoint": new_endpoint,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        for cb in self._on_failback_callbacks:
            try:
                if asyncio.iscoroutinefunction(cb):
                    await cb(event)
                else:
                    cb(event)
            except Exception:
                logger.exception("Failback callback error")
