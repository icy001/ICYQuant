"""
Stream Controller — operational control plane for the streaming platform,
managing stream lifecycle, resource allocation, and policy enforcement.

Commit 16 Part 1.4
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ControllerAction(str, Enum):
    CREATE = "create"
    ACTIVATE = "activate"
    PAUSE = "pause"
    RESUME = "resume"
    DRAIN = "drain"
    CLOSE = "close"
    DELETE = "delete"
    SCALE_UP = "scale_up"
    SCALE_DOWN = "scale_down"


@dataclass
class ControlEvent:
    """A control plane event."""
    action: ControllerAction
    topic: str
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    reason: str = ""
    details: dict[str, Any] = field(default_factory=dict)
    success: bool = True


@dataclass
class ResourceLimits:
    """Resource limits for the streaming platform."""
    max_streams: int = 1000
    max_partitions: int = 10000
    max_subscribers: int = 5000
    max_throughput_per_stream: int = 100000
    max_queue_depth: int = 1000000


class StreamController:
    """
    Operational control plane for the streaming platform.

    Manages resource allocation, enforces limits, and provides
    centralized stream lifecycle commands with audit trail.

    Usage::

        controller = StreamController()
        await controller.enforce_limits()
        event = await controller.execute(ControllerAction.PAUSE, "market.tick")
    """

    def __init__(self, limits: Optional[ResourceLimits] = None) -> None:
        self.limits = limits or ResourceLimits()
        self._events: list[ControlEvent] = []
        self._locks: dict[str, asyncio.Lock] = {}
        self._max_history = 10000

    async def execute(
        self,
        action: ControllerAction,
        topic: str,
        *,
        reason: str = "",
        details: Optional[dict[str, Any]] = None,
    ) -> ControlEvent:
        """Execute a control action for a topic."""
        if topic not in self._locks:
            self._locks[topic] = asyncio.Lock()

        async with self._locks[topic]:
            event = ControlEvent(
                action=action,
                topic=topic,
                reason=reason,
                details=details or {},
            )

            logger.info(
                "Controller action: %s on %s (reason: %s)",
                action.value, topic, reason or "N/A",
            )

            self._events.append(event)

            # Trim history
            if len(self._events) > self._max_history:
                self._events = self._events[-self._max_history:]

            return event

    async def enforce_limits(
        self,
        current_streams: int = 0,
        current_partitions: int = 0,
        current_subscribers: int = 0,
    ) -> dict[str, bool]:
        """Check and enforce resource limits."""
        checks = {
            "streams": current_streams < self.limits.max_streams,
            "partitions": current_partitions < self.limits.max_partitions,
            "subscribers": current_subscribers < self.limits.max_subscribers,
        }

        for resource, ok in checks.items():
            if not ok:
                logger.warning("Resource limit reached: %s", resource)

        return checks

    async def scale_partitions(self, topic: str, target_count: int) -> ControlEvent:
        """Request partition scaling for a topic."""
        return await self.execute(
            action=ControllerAction.SCALE_UP if target_count > 0 else ControllerAction.SCALE_DOWN,
            topic=topic,
            details={"target_partitions": target_count},
        )

    async def get_history(
        self,
        topic: Optional[str] = None,
        action: Optional[ControllerAction] = None,
        limit: int = 100,
    ) -> list[ControlEvent]:
        """Get control event history with optional filters."""
        results = self._events
        if topic:
            results = [e for e in results if e.topic == topic]
        if action:
            results = [e for e in results if e.action == action]
        return results[-limit:]

    async def clear_history(self) -> None:
        """Clear the control event history."""
        self._events.clear()
        logger.info("Control event history cleared.")
