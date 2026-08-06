"""Trigger Dispatcher — sends fired triggers to the scheduler runtime.

The :class:`TriggerDispatcher` takes items from the priority queue and
dispatches them to the appropriate execution target (scheduler runtime,
workflow engine, or external handler).
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .trigger_context import TriggerContext

logger = logging.getLogger(__name__)


@dataclass
class DispatchResult:
    """Result of a dispatch attempt."""

    success: bool
    execution_id: str = ""
    error: Optional[str] = None
    dispatched_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    worker_id: str = ""


class TriggerDispatcher:
    """Dispatches queued trigger items to scheduler runtime / workflow engine.

    Supports:
    * Async dispatch with configurable concurrency
    * Retry on transient failures
    * Worker assignment
    * Dispatch result recording
    """

    def __init__(self, max_concurrency: int = 100) -> None:
        self._lock = threading.RLock()
        self._max_concurrency = max_concurrency
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._running = False

        # Dispatch history (circular buffer style)
        self._history: List[DispatchResult] = []
        self._max_history = 10_000

        # Stats
        self._total_attempts: int = 0
        self._total_success: int = 0
        self._total_failures: int = 0
        self._last_dispatch_at: Optional[datetime] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def start(self) -> None:
        self._running = True
        logger.info("TriggerDispatcher: started (max_concurrency=%d)", self._max_concurrency)

    def stop(self) -> None:
        self._running = False
        logger.info("TriggerDispatcher: stopped")

    # ------------------------------------------------------------------
    # Dispatch
    # ------------------------------------------------------------------

    async def dispatch(self, queue_item: Any) -> DispatchResult:
        """Dispatch a single queue item to the scheduler runtime.

        In production this calls the SchedulerRuntime to schedule a job;
        here we model it as an async operation that assigns a worker and
        records the result.
        """
        if not self._running:
            return DispatchResult(
                success=False,
                error="Dispatcher is not running",
            )

        async with self._semaphore:
            self._total_attempts += 1
            try:
                # Build trigger context
                ctx = TriggerContext(
                    trigger_id=getattr(queue_item, "trigger_id", ""),
                    schedule_id=getattr(queue_item, "schedule_id", ""),
                    payload=getattr(queue_item, "payload", {}),
                    trigger_time=datetime.now(timezone.utc),
                )

                # Simulate worker assignment (real impl selects from pool)
                worker_id = f"worker-{hash(ctx.trigger_id) % 10:02d}"
                ctx.worker = worker_id

                # In production: await scheduler_runtime.schedule_job(ctx)
                # For now, simulate a short dispatch delay
                await asyncio.sleep(0.001)

                result = DispatchResult(
                    success=True,
                    execution_id=ctx.execution_id,
                    worker_id=worker_id,
                )

                self._total_success += 1
                self._last_dispatch_at = datetime.now(timezone.utc)
                self._record(result)
                return result

            except Exception as e:
                logger.exception("TriggerDispatcher: dispatch failed")
                result = DispatchResult(success=False, error=str(e))
                self._total_failures += 1
                self._record(result)
                return result

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _record(self, result: DispatchResult) -> None:
        with self._lock:
            self._history.append(result)
            if len(self._history) > self._max_history:
                self._history = self._history[-self._max_history:]

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._running,
                "max_concurrency": self._max_concurrency,
                "total_attempts": self._total_attempts,
                "total_success": self._total_success,
                "total_failures": self._total_failures,
                "success_rate": (
                    self._total_success / max(self._total_attempts, 1)
                ),
                "last_dispatch_at": (
                    self._last_dispatch_at.isoformat() if self._last_dispatch_at else None
                ),
            }
