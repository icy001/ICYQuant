"""Execution Queue — Priority execution queue with fair scheduling.

Manages the queue of pending execution tasks, ensuring fair dispatch
across strategies while respecting priority levels.

Features:
    - Priority-based ordering
    - Fair scheduling (prevents starvation)
    - Backpressure handling
    - Queue depth monitoring

Usage::

    queue = ExecutionQueue(max_size=1000)
    await queue.enqueue(task, priority=TaskPriority.HIGH)
    task = await queue.dequeue()
"""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any, Optional

from services.ems.execution_runtime import ExecutionTask
from services.ems.execution_scheduler import TaskPriority

logger = logging.getLogger(__name__)


class ExecutionQueue:
    """Priority execution queue with fair scheduling.

    Enqueues execution tasks and dequeues them in priority order
    with fairness guarantees to prevent starvation.

    Attributes:
        max_size: Maximum queue size (backpressure)
        _high: High priority queue
        _normal: Normal priority queue
        _low: Low priority queue
        _background: Background priority queue
        _fair_count: Round-robin counter per priority
        _lock: Async lock
        _not_empty: Condition for blocking dequeue
    """

    def __init__(self, max_size: int = 1000) -> None:
        self.max_size = max_size
        self._high: list[ExecutionTask] = []
        self._normal: list[ExecutionTask] = []
        self._low: list[ExecutionTask] = []
        self._background: list[ExecutionTask] = []
        self._fair_count: dict[str, int] = defaultdict(int)
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition(self._lock)

    # ── Queue Operations ───────────────────────────────────────────

    async def enqueue(self, task: ExecutionTask, priority: TaskPriority = TaskPriority.NORMAL) -> bool:
        """Add a task to the execution queue.

        Args:
            task: Execution task to enqueue
            priority: Task priority

        Returns:
            True if enqueued, False if queue is full
        """
        async with self._lock:
            if self.size >= self.max_size:
                logger.warning("Execution queue full: size=%d max=%d", self.size, self.max_size)
                return False

            queue = self._get_queue(priority)
            queue.append(task)
            self._not_empty.notify(1)

            logger.debug(
                "Task enqueued: task=%s priority=%s depth=%d",
                task.task_id,
                priority.name,
                self.size,
            )
            return True

    async def dequeue(self) -> Optional[ExecutionTask]:
        """Dequeue the next task in priority order with fairness.

        Uses weighted round-robin across priority levels:
        - HIGH: 50% of dispatch slots
        - NORMAL: 30%
        - LOW: 15%
        - BACKGROUND: 5%

        Returns:
            Next ExecutionTask, or None if queue is empty
        """
        async with self._not_empty:
            while self.size == 0:
                await self._not_empty.wait()

            task = self._select_next()
            if task:
                logger.debug("Task dequeued: task=%s", task.task_id)
            return task

    async def dequeue_nowait(self) -> Optional[ExecutionTask]:
        """Dequeue without blocking.

        Returns:
            Next ExecutionTask or None
        """
        async with self._lock:
            return self._select_next()

    async def remove(self, task_id: str) -> Optional[ExecutionTask]:
        """Remove a specific task from the queue.

        Args:
            task_id: Task identifier to remove

        Returns:
            Removed task or None
        """
        async with self._lock:
            for queue in [self._high, self._normal, self._low, self._background]:
                for i, task in enumerate(queue):
                    if task.task_id == task_id:
                        return queue.pop(i)
        return None

    async def clear(self) -> None:
        """Clear all tasks from the queue."""
        async with self._lock:
            self._high.clear()
            self._normal.clear()
            self._low.clear()
            self._background.clear()
            self._fair_count.clear()

    # ── Selection Logic ────────────────────────────────────────────

    def _get_queue(self, priority: TaskPriority) -> list[ExecutionTask]:
        """Get the queue list for a priority level."""
        mapping = {
            TaskPriority.HIGH: self._high,
            TaskPriority.NORMAL: self._normal,
            TaskPriority.LOW: self._low,
            TaskPriority.BACKGROUND: self._background,
        }
        return mapping[priority]

    def _select_next(self) -> Optional[ExecutionTask]:
        """Select next task with weighted fair scheduling.

        Weights: HIGH=50, NORMAL=30, LOW=15, BACKGROUND=5
        """
        # Track how many from each level we've served
        if self._fair_count["total"] >= 100:
            self._fair_count.clear()

        total = self._fair_count["total"]

        # Weighted selection
        if self._high and total % 100 < 50:
            task = self._high.pop(0)
        elif self._normal and total % 100 < 80:
            task = self._normal.pop(0)
        elif self._low and total % 100 < 95:
            task = self._low.pop(0)
        elif self._background:
            task = self._background.pop(0)
        else:
            # Fallback: pick from any non-empty queue
            for queue in [self._high, self._normal, self._low, self._background]:
                if queue:
                    task = queue.pop(0)
                    break
            else:
                return None

        self._fair_count["total"] += 1
        return task

    # ── Properties ─────────────────────────────────────────────────

    @property
    def size(self) -> int:
        """Total number of tasks in the queue."""
        return len(self._high) + len(self._normal) + len(self._low) + len(self._background)

    @property
    def is_full(self) -> bool:
        """Whether the queue is at capacity."""
        return self.size >= self.max_size

    @property
    def is_empty(self) -> bool:
        """Whether the queue is empty."""
        return self.size == 0

    def to_dict(self) -> dict[str, Any]:
        """Serialize queue state."""
        return {
            "size": self.size,
            "max_size": self.max_size,
            "high": len(self._high),
            "normal": len(self._normal),
            "low": len(self._low),
            "background": len(self._background),
            "is_full": self.is_full,
        }
