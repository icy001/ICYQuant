"""
Risk & Execution Runtime — concurrent task execution environment.

Manages async execution of risk calculations, execution plans, and
feedback processing with resource limits and timeout enforcement.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Callable, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Execution priority for runtime tasks."""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    BACKGROUND = 4


class TaskState(Enum):
    """Task lifecycle states."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass
class RuntimeTask:
    """A single runtime task."""
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    priority: TaskPriority = TaskPriority.MEDIUM
    state: TaskState = TaskState.PENDING
    created_at: datetime = field(default_factory=datetime.now)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    timeout_seconds: int = 300
    result: Any = None
    error: Optional[str] = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class RuntimeConfig:
    """Runtime configuration."""
    max_concurrent_tasks: int = 8
    task_timeout_seconds: int = 300
    queue_max_size: int = 1000
    worker_count: int = 4


class RiskExecutionRuntime:
    """
    Async task execution runtime for risk & execution operations.

    Features:
        - Priority-based task scheduling
        - Concurrency limiting
        - Timeout enforcement
        - Graceful cancellation
    """

    def __init__(self, config: Optional[RuntimeConfig] = None) -> None:
        self._config = config or RuntimeConfig()
        self._tasks: dict[str, RuntimeTask] = {}
        self._queue: asyncio.PriorityQueue = asyncio.PriorityQueue()
        self._semaphore = asyncio.Semaphore(self._config.max_concurrent_tasks)
        self._running = False
        self._workers: list[asyncio.Task] = []

    async def start(self) -> None:
        """Start the runtime workers."""
        self._running = True
        self._workers = [
            asyncio.create_task(self._worker(i))
            for i in range(self._config.worker_count)
        ]
        logger.info("RiskExecutionRuntime started workers=%d", self._config.worker_count)

    async def stop(self) -> None:
        """Gracefully stop the runtime."""
        self._running = False
        for worker in self._workers:
            worker.cancel()
        await asyncio.gather(*self._workers, return_exceptions=True)
        logger.info("RiskExecutionRuntime stopped")

    async def submit(
        self,
        coro: Callable,
        name: str = "",
        priority: TaskPriority = TaskPriority.MEDIUM,
        timeout: Optional[int] = None,
        metadata: Optional[dict] = None,
    ) -> RuntimeTask:
        """
        Submit a coroutine for execution.

        Returns a RuntimeTask that can be awaited for results.
        """
        task = RuntimeTask(
            name=name,
            priority=priority,
            timeout_seconds=timeout or self._config.task_timeout_seconds,
            metadata=metadata or {},
        )
        self._tasks[task.id] = task
        await self._queue.put((priority.value, task.id, coro, task))
        logger.debug("Task submitted id=%s name=%s priority=%s", task.id, name, priority)
        return task

    async def submit_and_wait(self, *args, **kwargs) -> Any:
        """Submit a task and wait for its result."""
        task = await self.submit(*args, **kwargs)
        while task.state in (TaskState.PENDING, TaskState.RUNNING):
            await asyncio.sleep(0.05)
        if task.state == TaskState.FAILED:
            raise RuntimeError(task.error or "Task failed")
        if task.state == TaskState.TIMED_OUT:
            raise TimeoutError(f"Task {task.id} timed out")
        return task.result

    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a pending task."""
        task = self._tasks.get(task_id)
        if task and task.state == TaskState.PENDING:
            task.state = TaskState.CANCELLED
            return True
        return False

    async def _worker(self, worker_id: int) -> None:
        """Background worker processing tasks from the queue."""
        while self._running:
            try:
                priority, task_id, coro, task = await asyncio.wait_for(
                    self._queue.get(), timeout=1.0
                )
            except asyncio.TimeoutError:
                continue

            if task.state == TaskState.CANCELLED:
                continue

            async with self._semaphore:
                task.state = TaskState.RUNNING
                task.started_at = datetime.now()
                try:
                    result = await asyncio.wait_for(
                        coro(), timeout=task.timeout_seconds
                    )
                    task.result = result
                    task.state = TaskState.COMPLETED
                except asyncio.TimeoutError:
                    task.state = TaskState.TIMED_OUT
                    task.error = f"Timed out after {task.timeout_seconds}s"
                except Exception as e:
                    task.state = TaskState.FAILED
                    task.error = str(e)
                    logger.error("Task failed id=%s error=%s", task_id, e)
                finally:
                    task.completed_at = datetime.now()

    @property
    def active_tasks(self) -> int:
        return sum(1 for t in self._tasks.values() if t.state == TaskState.RUNNING)

    @property
    def pending_tasks(self) -> int:
        return sum(1 for t in self._tasks.values() if t.state == TaskState.PENDING)

    def get_task(self, task_id: str) -> Optional[RuntimeTask]:
        return self._tasks.get(task_id)
