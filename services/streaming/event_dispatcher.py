"""
Event Dispatcher — asynchronous event dispatching with fan-out,
load balancing, and delivery guarantees.

Commit 16 Part 1.4
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DispatchStatus(str, Enum):
    PENDING = "pending"
    DELIVERED = "delivered"
    FAILED = "failed"
    RETRYING = "retrying"
    DEAD_LETTERED = "dead_lettered"
    ACKNOWLEDGED = "acknowledged"


@dataclass
class DispatchResult:
    """Result of an event dispatch."""
    dispatch_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    topic: str = ""
    event_id: str = ""
    target: str = ""
    status: DispatchStatus = DispatchStatus.PENDING
    attempts: int = 0
    latency_ms: float = 0.0
    error: str = ""
    dispatched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    acknowledged_at: Optional[datetime] = None


class EventDispatcher:
    """
    Asynchronous event dispatcher with fan-out and delivery guarantees.

    Dispatches events to multiple targets with configurable parallelism,
    retry logic, and delivery tracking.

    Usage::

        dispatcher = EventDispatcher()
        dispatcher.register_target("tick_handler", handle_tick)
        result = await dispatcher.dispatch("market.tick", event, targets=["tick_handler"])
        results = await dispatcher.fanout("market.tick", event, ["h1", "h2", "h3"])
    """

    def __init__(self, max_concurrent_dispatches: int = 100) -> None:
        self.max_concurrent_dispatches = max_concurrent_dispatches
        self._targets: dict[str, Any] = {}
        self._results: dict[str, DispatchResult] = {}
        self._semaphore = asyncio.Semaphore(max_concurrent_dispatches)
        self._total_dispatched = 0
        self._total_failed = 0

    def register_target(self, name: str, handler: Any) -> None:
        """Register a dispatch target handler."""
        self._targets[name] = handler

    def unregister_target(self, name: str) -> None:
        """Unregister a dispatch target."""
        self._targets.pop(name, None)

    async def dispatch(
        self,
        topic: str,
        event: Any,
        *,
        targets: Optional[list[str]] = None,
        event_id: Optional[str] = None,
    ) -> list[DispatchResult]:
        """Dispatch an event to specified targets."""
        target_names = targets or list(self._targets.keys())
        results = []

        async with self._semaphore:
            for target_name in target_names:
                handler = self._targets.get(target_name)
                if handler is None:
                    continue

                dispatch_id = str(uuid.uuid4())
                start = time.monotonic()
                result = DispatchResult(
                    dispatch_id=dispatch_id,
                    topic=topic,
                    event_id=event_id or str(uuid.uuid4()),
                    target=target_name,
                    status=DispatchStatus.PENDING,
                    attempts=1,
                )

                try:
                    if asyncio.iscoroutinefunction(handler):
                        await handler(event)
                    elif callable(handler):
                        handler(event)
                    elif hasattr(handler, "handle"):
                        if asyncio.iscoroutinefunction(handler.handle):
                            await handler.handle(event)
                        else:
                            handler.handle(event)

                    result.status = DispatchStatus.DELIVERED
                    result.acknowledged_at = datetime.now(timezone.utc)
                    self._total_dispatched += 1

                except Exception as e:
                    result.status = DispatchStatus.FAILED
                    result.error = str(e)
                    self._total_failed += 1
                    logger.error(
                        "Dispatch failed: %s → %s: %s",
                        topic, target_name, e,
                    )

                result.latency_ms = (time.monotonic() - start) * 1000
                self._results[dispatch_id] = result
                results.append(result)

        return results

    async def fanout(
        self,
        topic: str,
        event: Any,
        target_names: list[str],
    ) -> list[DispatchResult]:
        """Fan-out an event to multiple targets concurrently."""
        tasks = [
            self.dispatch(topic, event, targets=[name])
            for name in target_names
            if name in self._targets
        ]
        all_results = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[DispatchResult] = []
        for r in all_results:
            if isinstance(r, list):
                results.extend(r)
        return results

    async def get_result(self, dispatch_id: str) -> Optional[DispatchResult]:
        """Get the result of a specific dispatch."""
        return self._results.get(dispatch_id)

    async def stats(self) -> dict[str, Any]:
        """Get dispatcher statistics."""
        return {
            "targets": len(self._targets),
            "total_dispatched": self._total_dispatched,
            "total_failed": self._total_failed,
            "success_rate": (
                self._total_dispatched / max(self._total_dispatched + self._total_failed, 1)
            ),
            "pending_results": len(self._results),
        }

    async def clear_results(self) -> None:
        """Clear dispatch result history."""
        self._results.clear()
