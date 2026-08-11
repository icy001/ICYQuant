"""
Task scheduler for agent task dispatch and execution management.

Handles task queuing, prioritization, scheduling, and execution
within the AI Agent Platform.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from shared.exceptions import ICYQuantError

logger = logging.getLogger(__name__)


# ── Task Types ──


class TaskStatus(str, Enum):
    """Task lifecycle status."""

    PENDING = "pending"
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskPriority(int, Enum):
    """Task priority levels."""

    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    BACKGROUND = 4


@dataclass
class ScheduledTask:
    """A task scheduled for execution."""

    task_id: str = field(default_factory=lambda: uuid4().hex)
    name: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.MEDIUM
    session_id: str = ""
    agent_id: str = ""
    payload: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    retry_count: int = 0
    max_retries: int = 3
    timeout_seconds: Optional[float] = 300.0
    result: Any = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert task to dictionary."""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "status": self.status.value,
            "priority": self.priority.name,
            "session_id": self.session_id,
            "agent_id": self.agent_id,
            "retry_count": self.retry_count,
        }


# ── Task Scheduler ──


class TaskScheduler:
    """Task scheduler for managing agent task execution.

    Handles task queuing with priority ordering, execution dispatch,
    retry logic, and throughput management.

    Usage:
        scheduler = TaskScheduler()
        await scheduler.start()
        task = await scheduler.submit(ScheduledTask(name="analyze", ...))
        status = await scheduler.get_task(task.task_id)
        await scheduler.stop()
    """

    def __init__(self, max_queue_size: int = 1000) -> None:
        self.max_queue_size = max_queue_size
        self._queue: List[ScheduledTask] = []
        self._task_registry: Dict[str, ScheduledTask] = {}
        self._running: bool = False
        self._worker_task: Optional[asyncio.Task] = None
        self._stats: Dict[str, int] = {
            "submitted": 0,
            "completed": 0,
            "failed": 0,
            "cancelled": 0,
        }
        logger.info("TaskScheduler created")

    # ── Lifecycle ──

    async def start(self) -> None:
        """Start the scheduler worker."""
        if self._running:
            return
        self._running = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("TaskScheduler started")

    async def stop(self) -> None:
        """Stop the scheduler and cancel pending tasks."""
        self._running = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass

        # Cancel all pending tasks
        for task in self._queue:
            task.status = TaskStatus.CANCELLED
        self._queue.clear()

        logger.info(
            "TaskScheduler stopped",
            extra={"stats": self._stats},
        )

    # ── Task Submission ──

    async def submit(self, task: ScheduledTask) -> ScheduledTask:
        """Submit a task for scheduling.

        Args:
            task: The task to schedule.

        Returns:
            The submitted task with task_id assigned.

        Raises:
            ICYQuantError: If queue is full.
        """
        if len(self._queue) >= self.max_queue_size:
            raise ICYQuantError("Task queue is full")

        task.status = TaskStatus.QUEUED
        self._task_registry[task.task_id] = task
        self._queue.append(task)
        self._stats["submitted"] += 1

        # Sort by priority (lower number = higher priority)
        self._queue.sort(key=lambda t: t.priority.value)

        logger.debug(f"Task submitted: {task.task_id} [{task.name}]")
        return task

    async def submit_batch(self, tasks: List[ScheduledTask]) -> List[ScheduledTask]:
        """Submit multiple tasks at once."""
        results = []
        for task in tasks:
            result = await self.submit(task)
            results.append(result)
        return results

    # ── Task Management ──

    async def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Get a task by ID."""
        return self._task_registry.get(task_id)

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending or queued task."""
        task = self._task_registry.get(task_id)
        if not task:
            return False

        if task.status in (TaskStatus.PENDING, TaskStatus.QUEUED):
            task.status = TaskStatus.CANCELLED
            self._queue = [t for t in self._queue if t.task_id != task_id]
            self._stats["cancelled"] += 1
            logger.info(f"Task cancelled: {task_id}")
            return True

        return False

    # ── Query ──

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status."""
        return {
            "queue_size": len(self._queue),
            "max_queue_size": self.max_queue_size,
            "total_registered": len(self._task_registry),
            "stats": dict(self._stats),
            "top_tasks": [t.to_dict() for t in self._queue[:5]],
        }

    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Dict[str, Any]]:
        """List tasks, optionally filtered by status."""
        tasks = list(self._task_registry.values())
        if status:
            tasks = [t for t in tasks if t.status == status]
        return [t.to_dict() for t in tasks]

    # ── Worker ──

    async def _worker_loop(self) -> None:
        """Main worker loop for processing tasks."""
        logger.info("TaskScheduler worker started")
        while self._running:
            try:
                if self._queue:
                    task = self._queue.pop(0)
                    await self._execute_task(task)
                else:
                    await asyncio.sleep(0.1)
            except asyncio.CancelledError:
                break
            except Exception:
                logger.exception("TaskScheduler worker error")

    async def _execute_task(self, task: ScheduledTask) -> None:
        """Execute a single task."""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)
        logger.debug(f"Executing task: {task.task_id} [{task.name}]")

        try:
            # Execution would delegate to the actual agent/tool handler
            # For now, simulate task completion
            await asyncio.sleep(0.01)  # Placeholder for actual work

            task.status = TaskStatus.COMPLETED
            task.completed_at = datetime.now(timezone.utc)
            self._stats["completed"] += 1
            logger.debug(f"Task completed: {task.task_id}")

        except Exception as e:
            logger.error(f"Task failed: {task.task_id} - {e}")

            if task.retry_count < task.max_retries:
                task.retry_count += 1
                task.status = TaskStatus.RETRYING
                self._queue.append(task)
                logger.info(f"Task retrying: {task.task_id} (attempt {task.retry_count})")
            else:
                task.status = TaskStatus.FAILED
                task.error = str(e)
                self._stats["failed"] += 1

    # ── Status ──

    def get_summary(self) -> Dict[str, Any]:
        """Get scheduler summary."""
        return {
            "running": self._running,
            "queue_size": len(self._queue),
            "stats": dict(self._stats),
        }
