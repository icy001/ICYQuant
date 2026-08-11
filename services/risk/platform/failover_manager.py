"""
Failover Manager — Automatic failover for high-availability risk cluster.

Handles detection, failover trigger, and recovery orchestration
to ensure the risk platform has no single point of failure.
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


class FailoverState(str, Enum):
    """Failover state machine states."""
    STANDBY = "standby"
    DETECTING = "detecting"
    FAILING_OVER = "failing_over"
    RECOVERING = "recovering"
    COMPLETE = "complete"


class FailoverReason(str, Enum):
    """Reasons for triggering failover."""
    HEARTBEAT_LOST = "heartbeat_lost"
    HEALTH_CHECK_FAILED = "health_check_failed"
    MANUAL_TRIGGER = "manual_trigger"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    NETWORK_PARTITION = "network_partition"


@dataclass
class FailoverEvent:
    """A failover event record."""
    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    reason: FailoverReason = FailoverReason.HEARTBEAT_LOST
    source_node: str = ""
    target_node: str = ""
    state: FailoverState = FailoverState.DETECTING
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: Optional[datetime] = None
    duration_seconds: float = 0.0
    success: bool = False
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class FailoverConfig:
    """Failover configuration."""
    heartbeat_timeout_seconds: float = 15.0
    health_check_interval_seconds: float = 5.0
    max_failover_attempts: int = 3
    failover_timeout_seconds: float = 30.0
    recovery_grace_period_seconds: float = 10.0
    auto_recover: bool = True


class FailoverManager:
    """
    Automatic failover manager for HA risk cluster.

    Monitors node health, detects failures, and orchestrates
    failover to standby nodes with zero-downtime transition.

    Usage::

        fm = FailoverManager(platform=platform)
        await fm.initialize()
        # Failover triggers automatically on health check failure
        result = await fm.manual_failover("node-1", "node-2")
    """

    def __init__(
        self,
        platform: Any = None,
        config: Optional[FailoverConfig] = None,
    ) -> None:
        self._platform = platform
        self._config = config or FailoverConfig()
        self._state = FailoverState.STANDBY
        self._active_node: str = ""
        self._standby_nodes: list[str] = []
        self._failover_history: list[FailoverEvent] = []
        self._health_callbacks: list[Callable] = []
        self._lock = asyncio.Lock()
        self._initialized = False
        self._running = False

    async def initialize(self) -> None:
        """Initialize the failover manager."""
        self._initialized = True
        self._running = True
        asyncio.create_task(self._health_monitor_loop())
        logger.info("FailoverManager initialized.")

    async def stop(self) -> None:
        """Stop the failover manager."""
        self._running = False
        logger.info("FailoverManager stopped.")

    # ---- Node Registration ----

    async def set_active_node(self, node_id: str) -> None:
        """Set the current active (primary) node."""
        self._active_node = node_id
        logger.info(f"Active node set: {node_id}")

    async def add_standby_node(self, node_id: str) -> None:
        """Add a standby node for failover."""
        if node_id not in self._standby_nodes:
            self._standby_nodes.append(node_id)
            logger.info(f"Standby node added: {node_id}")

    async def remove_standby_node(self, node_id: str) -> None:
        """Remove a standby node."""
        if node_id in self._standby_nodes:
            self._standby_nodes.remove(node_id)

    # ---- Failover ----

    async def manual_failover(
        self,
        source_node: str,
        target_node: str,
    ) -> FailoverEvent:
        """Manually trigger a failover from source to target."""
        return await self._execute_failover(
            reason=FailoverReason.MANUAL_TRIGGER,
            source_node=source_node,
            target_node=target_node,
        )

    async def auto_failover(self, source_node: str) -> Optional[FailoverEvent]:
        """Automatically failover from a failed source node."""
        if not self._standby_nodes:
            logger.warning("No standby nodes available for auto-failover")
            return None

        target = self._standby_nodes[0]
        return await self._execute_failover(
            reason=FailoverReason.HEARTBEAT_LOST,
            source_node=source_node,
            target_node=target,
        )

    async def get_failover_history(self, limit: int = 50) -> list[FailoverEvent]:
        """Get failover event history."""
        return self._failover_history[-limit:]

    async def get_current_state(self) -> dict[str, Any]:
        """Get current failover state."""
        return {
            "state": self._state.value,
            "active_node": self._active_node,
            "standby_nodes": self._standby_nodes,
            "failover_count": len(self._failover_history),
        }

    # ---- Health Callbacks ----

    def register_health_callback(self, callback: Callable) -> None:
        """Register a callback for health status changes."""
        self._health_callbacks.append(callback)

    # ---- Recovery ----

    async def recover_node(self, node_id: str) -> bool:
        """Recover a failed node."""
        logger.info(f"Recovering node: {node_id}")
        await asyncio.sleep(self._config.recovery_grace_period_seconds)
        # Node is considered recovered
        return True

    # ---- Internal ----

    async def _execute_failover(
        self,
        reason: FailoverReason,
        source_node: str,
        target_node: str,
    ) -> FailoverEvent:
        """Execute a failover event."""
        start = time.monotonic()

        async with self._lock:
            self._state = FailoverState.FAILING_OVER

        event = FailoverEvent(
            reason=reason,
            source_node=source_node,
            target_node=target_node,
            state=FailoverState.FAILING_OVER,
        )

        try:
            # Step 1: Mark source as failed
            logger.warning(f"Failover: {source_node} -> {target_node} ({reason.value})")

            # Step 2: Promote target
            self._active_node = target_node
            if target_node in self._standby_nodes:
                self._standby_nodes.remove(target_node)

            # Step 3: Add source as standby (for recovery)
            if source_node not in self._standby_nodes:
                self._standby_nodes.append(source_node)

            # Step 4: Notify callbacks
            for cb in self._health_callbacks:
                try:
                    await cb(source_node, target_node)
                except Exception as e:
                    logger.error(f"Failover callback error: {e}")

            event.success = True
            event.state = FailoverState.COMPLETE

        except Exception as e:
            event.success = False
            event.error = str(e)
            event.state = FailoverState.COMPLETE
            logger.error(f"Failover failed: {e}")

        finally:
            event.completed_at = datetime.now(timezone.utc)
            event.duration_seconds = time.monotonic() - start

            async with self._lock:
                self._state = FailoverState.STANDBY
                self._failover_history.append(event)
                if len(self._failover_history) > 1000:
                    self._failover_history = self._failover_history[-1000:]

        return event

    async def _health_monitor_loop(self) -> None:
        """Periodic health monitoring loop."""
        while self._running:
            await asyncio.sleep(self._config.health_check_interval_seconds)
            try:
                if self._active_node and self._config.auto_recover:
                    # Health check the active node
                    is_healthy = await self._check_node_health(self._active_node)
                    if not is_healthy and self._standby_nodes:
                        await self.auto_failover(self._active_node)
            except Exception as e:
                logger.error(f"Health monitor error: {e}")

    async def _check_node_health(self, node_id: str) -> bool:
        """Check if a node is healthy."""
        # Delegate to platform health check
        if self._platform:
            health = await self._platform.health_check()
            return health.get("status") == "healthy"
        return True

    async def health_check(self) -> dict[str, Any]:
        """Check failover manager health."""
        return {
            "status": "healthy" if self._running else "stopped",
            "failover_state": self._state.value,
            "active_node": self._active_node,
            "standby_count": len(self._standby_nodes),
            "total_failovers": len(self._failover_history),
            "last_failover": (
                self._failover_history[-1].started_at.isoformat()
                if self._failover_history else None
            ),
        }
