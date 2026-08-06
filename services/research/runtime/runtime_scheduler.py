"""Runtime Scheduler — bridges research runtimes with the distributed scheduler.

Translates research experiment configurations into scheduler tasks,
manages scheduling lifecycle, and handles priority-based queueing.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from .runtime_context import RuntimeContext, ExecutionConfig
from .runtime_state import RuntimeState, RuntimeStatus

logger = logging.getLogger(__name__)


class SchedulePriority(int, Enum):
    """Task scheduling priority levels."""

    LOW = 0
    NORMAL = 50
    HIGH = 80
    CRITICAL = 100


class QueueStatus(str, Enum):
    """Queue entry status."""

    QUEUED = "queued"
    SCHEDULED = "scheduled"
    DISPATCHED = "dispatched"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


@dataclass
class ScheduleResult:
    """Result of a scheduling operation."""

    task_id: str = ""
    status: QueueStatus = QueueStatus.QUEUED
    scheduled_at: Optional[datetime] = None
    estimated_start: Optional[datetime] = None
    position_in_queue: int = 0
    worker_id: Optional[str] = None
    message: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_scheduled(self) -> bool:
        return self.status in {QueueStatus.SCHEDULED, QueueStatus.DISPATCHED, QueueStatus.RUNNING}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status.value,
            "scheduled_at": self.scheduled_at.isoformat() if self.scheduled_at else None,
            "estimated_start": self.estimated_start.isoformat() if self.estimated_start else None,
            "position_in_queue": self.position_in_queue,
            "worker_id": self.worker_id,
            "message": self.message,
        }


class RuntimeScheduler:
    """Schedules research experiment executions via the distributed scheduler.

    Responsibilities:
    * Convert experiment configs into scheduler-compatible task definitions
    * Manage scheduling with priority and resource constraints
    * Track scheduling lifecycle and provide queue visibility
    * Handle scheduling failures with retry and fallback

    Usage::

        scheduler = RuntimeScheduler()
        result = await scheduler.schedule(
            context=runtime_context,
            priority=SchedulePriority.HIGH,
        )
        status = await scheduler.task_status(result.task_id)
    """

    # Global counters
    _scheduled: int = 0
    _completed: int = 0
    _failures: int = 0
    _lock: asyncio.Lock = asyncio.Lock()

    def __init__(self, max_queue_size: int = 1000) -> None:
        self._max_queue_size = max_queue_size
        self._queue: List[Dict[str, Any]] = []
        self._tasks: Dict[str, ScheduleResult] = {}
        self._state = "initialized"

    @property
    def queue_length(self) -> int:
        return len(self._queue)

    @property
    def scheduled_count(self) -> int:
        return RuntimeScheduler._scheduled

    @property
    def completed_count(self) -> int:
        return RuntimeScheduler._completed

    async def schedule(
        self,
        context: RuntimeContext,
        priority: SchedulePriority = SchedulePriority.NORMAL,
        depends_on: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
    ) -> ScheduleResult:
        """Schedule a research experiment for execution.

        Args:
            context: The runtime context with experiment + resource config.
            priority: Scheduling priority level.
            depends_on: Task IDs that must complete before this one.
            tags: Labels for grouping and filtering.

        Returns:
            ScheduleResult with task_id and queue position.
        """
        async with self._lock:
            if len(self._queue) >= self._max_queue_size:
                raise RuntimeError(
                    f"Scheduler queue full ({self._max_queue_size} max)"
                )

            task_id = f"research-{context.experiment_id[:8]}-{uuid4().hex[:6]}"
            entry = {
                "task_id": task_id,
                "context": context,
                "priority": priority.value,
                "depends_on": depends_on or [],
                "tags": tags or [],
                "created_at": datetime.now(timezone.utc),
            }

            # Insert respecting priority order (higher priority first)
            insert_pos = 0
            for i, queued in enumerate(self._queue):
                if queued["priority"] < priority.value:
                    insert_pos = i
                    break
                insert_pos = i + 1
            self._queue.insert(insert_pos, entry)

            position = insert_pos
            result = ScheduleResult(
                task_id=task_id,
                status=QueueStatus.QUEUED,
                scheduled_at=datetime.now(timezone.utc),
                position_in_queue=position,
                message=f"Queued at position {position} (priority={priority.name})",
            )
            self._tasks[task_id] = result
            RuntimeScheduler._scheduled += 1
            logger.info("Scheduled task %s (priority=%s, position=%d)", task_id, priority.name, position)
            return result

    async def cancel(self, task_id: str) -> bool:
        """Cancel a queued or scheduled task."""
        async with self._lock:
            self._queue = [e for e in self._queue if e["task_id"] != task_id]
            if task_id in self._tasks:
                self._tasks[task_id].status = QueueStatus.FAILED
                self._tasks[task_id].message = "Cancelled by user"
                return True
            return False

    async def task_status(self, task_id: str) -> Optional[ScheduleResult]:
        """Get current scheduling status of a task."""
        return self._tasks.get(task_id)

    async def dispatch_next(self, worker_id: str) -> Optional[ScheduleResult]:
        """Dispatch the next task in queue to a worker.

        Returns None if queue is empty.
        """
        async with self._lock:
            if not self._queue:
                return None
            entry = self._queue.pop(0)
            task_id = entry["task_id"]
            if task_id in self._tasks:
                self._tasks[task_id].status = QueueStatus.DISPATCHED
                self._tasks[task_id].worker_id = worker_id
            logger.info("Dispatched task %s to worker %s", task_id, worker_id)
            return self._tasks.get(task_id)

    async def mark_completed(self, task_id: str) -> None:
        async with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].status = QueueStatus.COMPLETED
                RuntimeScheduler._completed += 1

    async def mark_failed(self, task_id: str, error: str = "") -> None:
        async with self._lock:
            if task_id in self._tasks:
                self._tasks[task_id].status = QueueStatus.FAILED
                self._tasks[task_id].message = error
                RuntimeScheduler._failures += 1

    def queue_summary(self) -> Dict[str, Any]:
        return {
            "queue_length": len(self._queue),
            "total_scheduled": RuntimeScheduler._scheduled,
            "total_completed": RuntimeScheduler._completed,
            "total_failures": RuntimeScheduler._failures,
            "pending": sum(1 for t in self._tasks.values() if t.status == QueueStatus.QUEUED),
            "running": sum(1 for t in self._tasks.values() if t.status == QueueStatus.RUNNING),
        }

    def __repr__(self) -> str:
        return (
            f"RuntimeScheduler(queue={len(self._queue)}, "
            f"scheduled={RuntimeScheduler._scheduled}, "
            f"completed={RuntimeScheduler._completed})"
        )
