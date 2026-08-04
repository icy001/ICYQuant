"""
Secrets scheduler for periodic operations.

Provides async task scheduling infrastructure
for secret expiration checks, rotation scheduling,
lease renewal, and health checks. Supports graceful
shutdown, task status tracking, and thread-safe operation.
"""

from __future__ import annotations

import asyncio
import logging
import threading
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskType(str, Enum):
    """Built-in task types."""

    EXPIRATION_CHECK = "expiration_check"
    ROTATION_SCHEDULE = "rotation_schedule"
    LEASE_RENEWAL = "lease_renewal"
    HEALTH_CHECK = "health_check"
    CACHE_CLEANUP = "cache_cleanup"
    CUSTOM = "custom"


@dataclass
class TaskEntry:
    """
    A scheduled task entry.

    Attributes:
        task_id: Unique task identifier.
        name: Human-readable task name.
        task_type: Type of the task.
        fn: Async callable to execute.
        interval_seconds: Interval between executions.
        last_run_at: Last execution timestamp.
        next_run_at: Next scheduled execution.
        status: Current task status.
        run_count: Total execution count.
        failure_count: Consecutive failure count.
        last_duration_ms: Last execution duration in ms.
        metadata: Additional context.
    """

    task_id: str = ""
    name: str = ""
    task_type: TaskType = TaskType.CUSTOM
    fn: Optional[Callable] = None
    interval_seconds: float = 60.0
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    status: TaskStatus = TaskStatus.PENDING
    run_count: int = 0
    failure_count: int = 0
    last_duration_ms: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def is_due(self, now: Optional[datetime] = None) -> bool:
        """Check if the task is due for execution."""
        if self.status == TaskStatus.CANCELLED:
            return False
        if self.next_run_at is None:
            return True
        if now is None:
            now = datetime.utcnow()
        return now >= self.next_run_at

    def calculate_next_run(
        self,
        now: Optional[datetime] = None,
    ) -> datetime:
        """Calculate the next run time."""
        if now is None:
            now = datetime.utcnow()
        base = self.last_run_at or now
        return base + timedelta(seconds=self.interval_seconds)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "task_id": self.task_id,
            "name": self.name,
            "task_type": self.task_type.value,
            "interval_seconds": self.interval_seconds,
            "last_run_at": (
                self.last_run_at.isoformat() + "Z"
                if self.last_run_at
                else None
            ),
            "next_run_at": (
                self.next_run_at.isoformat() + "Z"
                if self.next_run_at
                else None
            ),
            "status": self.status.value,
            "run_count": self.run_count,
            "failure_count": self.failure_count,
            "last_duration_ms": self.last_duration_ms,
        }


class SecretsScheduler:
    """
    Secrets periodic task scheduler.

    Manages async periodic tasks for secret
    operations including expiration checks,
    rotation scheduling, lease renewal, and
    health checks. Provides thread-safe
    registration, cancellation, and graceful
    shutdown support.

    Usage:
        scheduler = SecretsScheduler()
        scheduler.register_task(
            name="expiration_check",
            fn=expiration_check_fn,
            interval_seconds=300,
        )
        await scheduler.start()
        # ... later
        await scheduler.shutdown()
    """

    MAX_FAILURES = 10
    DEFAULT_CHECK_INTERVAL = 5.0

    def __init__(
        self,
        check_interval: float = DEFAULT_CHECK_INTERVAL,
    ) -> None:
        """
        Initialize the scheduler.

        Args:
            check_interval: How often to check for due tasks (seconds).
        """
        self._check_interval = check_interval
        self._tasks: Dict[str, TaskEntry] = {}
        self._lock = threading.RLock()
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._shutdown_event = asyncio.Event()
        self._active_tasks: Dict[str, asyncio.Task] = {}

    @property
    def is_running(self) -> bool:
        """Check if the scheduler is running."""
        return self._running

    def register_task(
        self,
        fn: Callable,
        name: str = "",
        task_type: TaskType = TaskType.CUSTOM,
        interval_seconds: float = 60.0,
        immediate: bool = False,
        **metadata: Any,
    ) -> TaskEntry:
        """
        Register a new periodic task.

        Args:
            fn: Async callable to execute periodically.
            name: Human-readable task name.
            task_type: Type of the task.
            interval_seconds: Interval between executions.
            immediate: Whether to run immediately on start.
            **metadata: Additional context.

        Returns:
            The created TaskEntry.

        Raises:
            ValueError: If a task with the same name already exists.
        """
        with self._lock:
            if name and any(
                t.name == name for t in self._tasks.values()
            ):
                raise ValueError(
                    f"Task with name '{name}' already exists"
                )

            task_id = uuid.uuid4().hex[:12]
            entry = TaskEntry(
                task_id=task_id,
                name=name or task_id,
                task_type=task_type,
                fn=fn,
                interval_seconds=interval_seconds,
                next_run_at=(
                    datetime.utcnow()
                    if immediate
                    else datetime.utcnow()
                    + timedelta(seconds=interval_seconds)
                ),
                metadata=metadata,
            )

            self._tasks[task_id] = entry
            logger.info(
                "Task registered: %s (%s, type=%s, interval=%.1fs)",
                entry.name,
                task_id,
                task_type.value,
                interval_seconds,
            )
            return entry

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a registered task.

        Args:
            task_id: The task identifier.

        Returns:
            True if the task was found and cancelled.
        """
        with self._lock:
            entry = self._tasks.get(task_id)
            if entry is None:
                return False

            entry.status = TaskStatus.CANCELLED
            entry.fn = None

            # Cancel any currently running execution
            active = self._active_tasks.pop(task_id, None)
            if active and not active.done():
                active.cancel()

            logger.info("Task cancelled: %s (%s)", entry.name, task_id)
            return True

    def get_task(self, task_id: str) -> Optional[TaskEntry]:
        """
        Get a task by ID.

        Args:
            task_id: The task identifier.

        Returns:
            TaskEntry or None.
        """
        with self._lock:
            return self._tasks.get(task_id)

    def list_tasks(self) -> List[Dict[str, Any]]:
        """
        List all registered tasks.

        Returns:
            List of task info dictionaries.
        """
        with self._lock:
            return [t.to_dict() for t in self._tasks.values()]

    def get_due_tasks(self) -> List[TaskEntry]:
        """
        Get all tasks that are due for execution.

        Returns:
            List of due TaskEntry objects.
        """
        with self._lock:
            now = datetime.utcnow()
            return [
                t
                for t in self._tasks.values()
                if t.is_due(now)
            ]

    async def start(self) -> None:
        """
        Start the scheduler loop.

        Begins periodic task checking and execution.
        """
        if self._running:
            return

        self._running = True
        self._shutdown_event.clear()
        logger.info(
            "Secrets scheduler started (check_interval=%.1fs)",
            self._check_interval,
        )
        self._task = asyncio.create_task(self._scheduler_loop())

    async def shutdown(self, timeout: float = 30.0) -> None:
        """
        Gracefully shut down the scheduler.

        Cancels the main loop and waits for all
        active tasks to complete within the timeout.

        Args:
            timeout: Maximum seconds to wait for active tasks.
        """
        if not self._running:
            return

        logger.info("Secrets scheduler shutting down...")

        self._running = False
        self._shutdown_event.set()

        # Cancel the main loop
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        # Cancel and wait for active tasks
        active = list(self._active_tasks.items())
        if active:
            logger.info(
                "Waiting for %d active task(s) to complete...",
                len(active),
            )
            for task_id, task in active:
                if not task.done():
                    task.cancel()
                    try:
                        await asyncio.wait_for(
                            task, timeout=timeout
                        )
                    except asyncio.TimeoutError:
                        logger.warning(
                            "Task %s did not complete within timeout",
                            task_id,
                        )
                    except asyncio.CancelledError:
                        pass

        # Mark remaining tasks as cancelled
        with self._lock:
            for entry in self._tasks.values():
                if entry.status == TaskStatus.RUNNING:
                    entry.status = TaskStatus.CANCELLED

        self._active_tasks.clear()
        logger.info("Secrets scheduler stopped")

    async def _scheduler_loop(self) -> None:
        """Main scheduler loop - checks for and executes due tasks."""
        while self._running:
            try:
                due = self.get_due_tasks()
                for entry in due:
                    self._execute_task(entry)
            except Exception as e:
                logger.error(
                    "Scheduler loop error: %s", e,
                )

            try:
                await asyncio.wait_for(
                    self._shutdown_event.wait(),
                    timeout=self._check_interval,
                )
                break  # shutdown event set
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

    def _execute_task(self, entry: TaskEntry) -> None:
        """
        Launch a task execution without blocking the loop.

        Args:
            entry: Task to execute.
        """
        with self._lock:
            if entry.status == TaskStatus.CANCELLED:
                return
            entry.status = TaskStatus.RUNNING

        task = asyncio.create_task(self._run_task(entry))
        self._active_tasks[entry.task_id] = task
        task.add_done_callback(
            lambda t, eid=entry.task_id: self._on_task_done(eid, t)
        )

    async def _run_task(self, entry: TaskEntry) -> None:
        """
        Execute a single task with timing and error handling.

        Args:
            entry: Task to execute.
        """
        if entry.fn is None:
            return

        start = time.time()
        try:
            result = entry.fn()
            if asyncio.iscoroutine(result):
                result = await result

            with self._lock:
                entry.status = TaskStatus.COMPLETED
                entry.failure_count = 0
                entry.run_count += 1
                entry.last_duration_ms = (
                    time.time() - start
                ) * 1000
                entry.last_run_at = datetime.utcnow()
                entry.next_run_at = entry.calculate_next_run()

        except asyncio.CancelledError:
            with self._lock:
                entry.status = TaskStatus.CANCELLED
            logger.info(
                "Task cancelled: %s", entry.name,
            )

        except Exception as e:
            with self._lock:
                entry.status = TaskStatus.FAILED
                entry.failure_count += 1
                entry.run_count += 1
                entry.last_duration_ms = (
                    time.time() - start
                ) * 1000
                entry.last_run_at = datetime.utcnow()
                entry.next_run_at = entry.calculate_next_run()

                if entry.failure_count >= self.MAX_FAILURES:
                    logger.error(
                        "Task %s exceeded max failures (%d), disabling",
                        entry.name,
                        self.MAX_FAILURES,
                    )
                    entry.status = TaskStatus.CANCELLED
                    entry.fn = None

            logger.error(
                "Task execution failed for %s: %s",
                entry.name,
                e,
            )

    def _on_task_done(
        self,
        task_id: str,
        task: asyncio.Task,
    ) -> None:
        """
        Handle task completion cleanup.

        Args:
            task_id: The task identifier.
            task: The completed asyncio Task.
        """
        self._active_tasks.pop(task_id, None)
        try:
            task.result()
        except asyncio.CancelledError:
            pass
        except Exception:
            pass

    def get_status(self) -> Dict[str, Any]:
        """
        Get the scheduler status summary.

        Returns:
            Status dictionary with task counts and state.
        """
        with self._lock:
            status_counts: Dict[str, int] = {}
            for t in self._tasks.values():
                s = t.status.value
                status_counts[s] = status_counts.get(s, 0) + 1

            return {
                "running": self._running,
                "total_tasks": len(self._tasks),
                "active_executions": len(self._active_tasks),
                "by_status": status_counts,
                "check_interval_seconds": self._check_interval,
            }

    def get_stats(self) -> Dict[str, Any]:
        """
        Get scheduler statistics.

        Returns:
            Statistics dictionary.
        """
        with self._lock:
            total = len(self._tasks)
            by_type: Dict[str, int] = {}
            total_runs = 0
            total_failures = 0

            for t in self._tasks.values():
                tt = t.task_type.value
                by_type[tt] = by_type.get(tt, 0) + 1
                total_runs += t.run_count
                total_failures += t.failure_count

            return {
                "total_tasks": total,
                "by_type": by_type,
                "total_runs": total_runs,
                "total_failures": total_failures,
                "running": self._running,
                "check_interval_seconds": self._check_interval,
            }