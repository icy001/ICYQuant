"""Trigger Scheduler — bridge between the priority queue and the scheduler runtime.

The :class:`TriggerScheduler` pulls items from the priority queue and
hands them off to the scheduler runtime / workflow engine.  It manages
concurrency, worker selection, and backpressure.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .priority_queue import PriorityQueue, QueueItem

logger = logging.getLogger(__name__)


@dataclass
class ScheduleResult:
    """Result of scheduling a trigger item."""

    success: bool
    execution_id: str = ""
    worker_id: str = ""
    error: Optional[str] = None
    scheduled_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class TriggerScheduler:
    """Schedules queued trigger items onto workers / the workflow engine.

    Responsibilities:
    * Pull from priority queue
    * Worker selection (round-robin)
    * Concurrency control
    * Backpressure management

    Usage::

        scheduler = TriggerScheduler(queue, max_concurrency=50)
        await scheduler.start()
        # items are automatically pulled from queue and dispatched
    """

    def __init__(
        self,
        queue: PriorityQueue,
        max_concurrency: int = 100,
        poll_interval_ms: int = 100,
    ) -> None:
        self._lock = threading.RLock()
        self._queue = queue
        self._max_concurrency = max_concurrency
        self._poll_interval_ms = poll_interval_ms
        self._semaphore = asyncio.Semaphore(max_concurrency)
        self._running = False

        # Worker round-robin
        self._worker_count = 10
        self._worker_index: int = 0

        # Stats
        self._total_scheduled: int = 0
        self._total_success: int = 0
        self._total_failures: int = 0
        self._last_scheduled_at: Optional[datetime] = None

        self._scheduler_task: Optional[asyncio.Task] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def start(self) -> None:
        self._running = True
        self._scheduler_task = asyncio.create_task(self._run_loop())
        logger.info("TriggerScheduler: started (max_concurrency=%d)", self._max_concurrency)

    async def stop(self) -> None:
        self._running = False
        if self._scheduler_task and not self._scheduler_task.done():
            self._scheduler_task.cancel()
            try:
                await self._scheduler_task
            except asyncio.CancelledError:
                pass
        logger.info("TriggerScheduler: stopped")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def _run_loop(self) -> None:
        """Background loop: pull from queue → schedule."""
        while self._running:
            try:
                if self._queue.is_empty():
                    await asyncio.sleep(self._poll_interval_ms / 1000.0)
                    continue

                async with self._semaphore:
                    item = self._queue.pop()
                    if item is None:
                        await asyncio.sleep(0.01)
                        continue

                    result = await self._schedule_item(item)
                    if result.success:
                        self._total_success += 1
                    else:
                        self._total_failures += 1
                        logger.warning(
                            "TriggerScheduler: schedule failed trigger_id=%s error=%s",
                            item.trigger_id,
                            result.error,
                        )

                    self._total_scheduled += 1
                    self._last_scheduled_at = datetime.now(timezone.utc)

            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("TriggerScheduler: loop error")
                await asyncio.sleep(1.0)

    # ------------------------------------------------------------------
    # Schedule
    # ------------------------------------------------------------------

    async def _schedule_item(self, item: QueueItem) -> ScheduleResult:
        """Schedule a single queue item for execution.

        In production this calls into SchedulerRuntime to create a job
        execution.  Worker is selected via round-robin.
        """
        worker_id = self._next_worker()

        try:
            # Simulate async scheduling to the runtime
            await asyncio.sleep(0.001)

            return ScheduleResult(
                success=True,
                execution_id=f"exec-{item.trigger_id}-{self._total_scheduled}",
                worker_id=worker_id,
            )
        except Exception as e:
            return ScheduleResult(
                success=False,
                error=str(e),
            )

    # ------------------------------------------------------------------
    # Worker selection
    # ------------------------------------------------------------------

    def _next_worker(self) -> str:
        with self._lock:
            worker_id = f"worker-{self._worker_index:02d}"
            self._worker_index = (self._worker_index + 1) % self._worker_count
            return worker_id

    # ------------------------------------------------------------------
    # Query
    # ------------------------------------------------------------------

    @property
    def active_count(self) -> int:
        return self._max_concurrency - self._semaphore._value  # type: ignore[attr-defined]

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_report(self) -> Dict[str, Any]:
        return {
            "running": self._running,
            "max_concurrency": self._max_concurrency,
            "active_count": self.active_count,
            "total_scheduled": self._total_scheduled,
            "total_success": self._total_success,
            "total_failures": self._total_failures,
            "success_rate": (
                self._total_success / max(self._total_scheduled, 1)
            ),
            "last_scheduled_at": (
                self._last_scheduled_at.isoformat() if self._last_scheduled_at else None
            ),
            "queue": self._queue.health_report(),
        }
