"""Execution Scheduler — Multi-strategy execution scheduler.

Schedules the timing and ordering of child order dispatch across
multiple concurrent execution tasks. Supports priority-based scheduling
and fair allocation of dispatch slots.

Architecture::

    Execution Tasks → Priority Queue → Scheduler → Dispatch Slot → Child Order

Usage::

    scheduler = ExecutionScheduler(max_concurrent=10)
    await scheduler.schedule(task)
    next_slot = await scheduler.next_dispatch_slot()
"""

from __future__ import annotations

import asyncio
import heapq
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from services.ems.execution_runtime import ExecutionTask

logger = logging.getLogger(__name__)


class TaskPriority(int, Enum):
    """Execution task priority levels.

    HIGH: Urgent execution (e.g., risk reduction)
    NORMAL: Standard execution
    LOW: Non-urgent execution
    BACKGROUND: Passive/opportunistic execution
    """

    HIGH = 0
    NORMAL = 10
    LOW = 20
    BACKGROUND = 30


@dataclass(order=True)
class _ScheduledTask:
    """Internal priority queue entry."""

    priority: int
    timestamp: float
    task_id: str = field(compare=False)
    parent_order_id: str = field(compare=False)


class ExecutionScheduler:
    """Multi-strategy execution scheduler.

    Manages dispatch scheduling across concurrent execution tasks using
    a priority queue. Higher priority tasks get more dispatch slots.

    Attributes:
        max_concurrent: Maximum concurrent dispatch operations
        dispatch_interval_seconds: Minimum interval between dispatches
        _queue: Priority queue of scheduled tasks
        _priorities: Task priority assignments
        _last_dispatch: Last dispatch timestamp per task
        _dispatch_count: Dispatch count per task
        _lock: Async lock for thread safety
    """

    def __init__(
        self,
        max_concurrent: int = 10,
        dispatch_interval_seconds: float = 0.1,
    ) -> None:
        self.max_concurrent = max_concurrent
        self.dispatch_interval_seconds = dispatch_interval_seconds
        self._queue: list[_ScheduledTask] = []
        self._priorities: dict[str, TaskPriority] = {}
        self._last_dispatch: dict[str, float] = {}
        self._dispatch_count: dict[str, int] = {}
        self._active_slots = 0
        self._lock = asyncio.Lock()

    # ── Scheduling API ─────────────────────────────────────────────

    async def schedule(self, task: ExecutionTask, priority: TaskPriority = TaskPriority.NORMAL) -> None:
        """Register a task for scheduling.

        Args:
            task: Execution task to schedule
            priority: Task priority level
        """
        async with self._lock:
            self._priorities[task.task_id] = priority
            self._dispatch_count[task.task_id] = 0
            self._last_dispatch[task.task_id] = 0.0

            entry = _ScheduledTask(
                priority=priority.value,
                timestamp=time.monotonic(),
                task_id=task.task_id,
                parent_order_id=task.parent_order_id,
            )
            heapq.heappush(self._queue, entry)

            logger.debug(
                "Task scheduled: task=%s priority=%s",
                task.task_id,
                priority.name,
            )

    async def unschedule(self, task_id: str) -> None:
        """Remove a task from the scheduler.

        Args:
            task_id: Task to remove
        """
        async with self._lock:
            self._priorities.pop(task_id, None)
            self._last_dispatch.pop(task_id, None)
            self._dispatch_count.pop(task_id, None)

            # Rebuild queue without the removed task
            self._queue = [e for e in self._queue if e.task_id != task_id]
            heapq.heapify(self._queue)

    async def next_dispatch_slot(self) -> Optional[str]:
        """Get the next task ID eligible for dispatch.

        Uses round-robin within the same priority level for fairness.

        Returns:
            Task ID of next task to dispatch, or None if no tasks ready
        """
        async with self._lock:
            if not self._queue or self._active_slots >= self.max_concurrent:
                return None

            now = time.monotonic()

            # Find eligible tasks (enough time since last dispatch)
            eligible: list[_ScheduledTask] = []
            for _ in range(len(self._queue)):
                entry = heapq.heappop(self._queue)
                last = self._last_dispatch.get(entry.task_id, 0.0)
                if now - last >= self.dispatch_interval_seconds:
                    eligible.append(entry)
                else:
                    heapq.heappush(self._queue, entry)

            if not eligible:
                return None

            # Pick lowest priority (highest urgency) + oldest timestamp
            best = min(eligible, key=lambda e: (e.priority, e.timestamp))

            # Re-queue non-selected entries
            for entry in eligible:
                if entry.task_id != best.task_id:
                    heapq.heappush(self._queue, entry)

            # Update dispatch tracking
            self._last_dispatch[best.task_id] = now
            self._dispatch_count[best.task_id] = self._dispatch_count.get(best.task_id, 0) + 1
            self._active_slots += 1

            # Re-queue for next round (with updated timestamp)
            heapq.heappush(
                self._queue,
                _ScheduledTask(
                    priority=best.priority,
                    timestamp=now,
                    task_id=best.task_id,
                    parent_order_id=best.parent_order_id,
                ),
            )

            return best.task_id

    def release_slot(self) -> None:
        """Release a dispatch slot back to the pool."""
        self._active_slots = max(0, self._active_slots - 1)

    # ── Priority Management ────────────────────────────────────────

    async def set_priority(self, task_id: str, priority: TaskPriority) -> None:
        """Update task priority.

        Args:
            task_id: Task to update
            priority: New priority level
        """
        async with self._lock:
            self._priorities[task_id] = priority

    async def promote(self, task_id: str) -> None:
        """Promote task priority (e.g., for urgent execution).

        Moves priority up one level.

        Args:
            task_id: Task to promote
        """
        current = self._priorities.get(task_id, TaskPriority.NORMAL)
        if current == TaskPriority.HIGH:
            return  # Already highest
        new_priority = TaskPriority(max(0, current.value - 10))
        await self.set_priority(task_id, new_priority)
        logger.info("Task promoted: task=%s %s → %s", task_id, current.name, new_priority.name)

    # ── Query API ──────────────────────────────────────────────────

    async def get_queue_depth(self) -> int:
        """Get current number of tasks in the queue."""
        async with self._lock:
            return len(self._queue)

    async def get_dispatch_count(self, task_id: str) -> int:
        """Get dispatch count for a task."""
        return self._dispatch_count.get(task_id, 0)

    def to_dict(self) -> dict[str, Any]:
        """Serialize scheduler state."""
        return {
            "max_concurrent": self.max_concurrent,
            "queue_depth": len(self._queue),
            "active_slots": self._active_slots,
            "dispatch_counts": dict(self._dispatch_count),
        }
