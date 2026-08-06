"""
Task Executor — unified task execution with timeout, retry, and cancellation support.

Provides a consistent interface for executing individual workflow nodes.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, Optional

logger = logging.getLogger(__name__)


class TaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    TIMED_OUT = "timed_out"


@dataclass
class TaskResult:
    """Result of a task execution."""

    success: bool
    status: TaskStatus
    output: Any = None
    error: Optional[str] = None
    duration_ms: float = 0.0
    retry_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskConfig:
    """Configuration for task execution."""

    timeout_seconds: Optional[float] = None
    max_retries: int = 0
    retry_delay_seconds: float = 1.0
    retry_backoff: float = 2.0
    cancellable: bool = True


class TaskExecutor:
    """
    Executes individual tasks with built-in timeout, retry, and cancellation.

    Usage:
        executor = TaskExecutor(config=TaskConfig(timeout_seconds=30, max_retries=3))
        result = await executor.execute(my_async_fn, arg1, arg2)
    """

    def __init__(self, config: Optional[TaskConfig] = None):
        self.config = config or TaskConfig()
        self._cancel_events: Dict[str, asyncio.Event] = {}

    async def execute(
        self,
        task_fn: Callable[..., Any],
        *args,
        task_id: Optional[str] = None,
        **kwargs,
    ) -> TaskResult:
        """
        Execute a task with timeout, retry, and cancellation.

        Args:
            task_fn: The function to execute (sync or async).
            *args: Positional arguments for the function.
            task_id: Optional task identifier for cancellation.
            **kwargs: Keyword arguments for the function.

        Returns:
            TaskResult with execution outcome.
        """
        import time

        tid = task_id or f"task_{id(task_fn)}"
        retry_count = 0
        last_error = None

        while retry_count <= self.config.max_retries:
            start = time.monotonic()

            try:
                # Create cancellation event
                cancel_event = asyncio.Event()
                self._cancel_events[tid] = cancel_event

                # Execute with timeout
                coro = self._run_task(task_fn, *args, cancel_event=cancel_event, **kwargs)

                if self.config.timeout_seconds:
                    output = await asyncio.wait_for(coro, timeout=self.config.timeout_seconds)
                else:
                    output = await coro

                duration = (time.monotonic() - start) * 1000
                return TaskResult(
                    success=True,
                    status=TaskStatus.COMPLETED,
                    output=output,
                    duration_ms=duration,
                    retry_count=retry_count,
                )

            except asyncio.CancelledError:
                duration = (time.monotonic() - start) * 1000
                return TaskResult(
                    success=False,
                    status=TaskStatus.CANCELLED,
                    error="Task was cancelled",
                    duration_ms=duration,
                    retry_count=retry_count,
                )

            except asyncio.TimeoutError:
                duration = (time.monotonic() - start) * 1000
                last_error = f"Task timed out after {self.config.timeout_seconds}s"
                logger.warning(f"{last_error} (retry {retry_count}/{self.config.max_retries})")
                retry_count += 1

                if retry_count <= self.config.max_retries:
                    delay = self.config.retry_delay_seconds * (self.config.retry_backoff ** (retry_count - 1))
                    await asyncio.sleep(delay)
                else:
                    return TaskResult(
                        success=False,
                        status=TaskStatus.TIMED_OUT,
                        error=last_error,
                        duration_ms=duration,
                        retry_count=retry_count,
                    )

            except Exception as e:
                duration = (time.monotonic() - start) * 1000
                last_error = str(e)
                logger.error(f"Task failed: {e} (retry {retry_count}/{self.config.max_retries})")
                retry_count += 1

                if retry_count <= self.config.max_retries:
                    delay = self.config.retry_delay_seconds * (self.config.retry_backoff ** (retry_count - 1))
                    await asyncio.sleep(delay)
                else:
                    return TaskResult(
                        success=False,
                        status=TaskStatus.FAILED,
                        error=last_error,
                        duration_ms=duration,
                        retry_count=retry_count,
                    )

            finally:
                self._cancel_events.pop(tid, None)

        return TaskResult(
            success=False,
            status=TaskStatus.FAILED,
            error=last_error or "Unknown error",
            retry_count=retry_count,
        )

    async def _run_task(
        self,
        task_fn: Callable,
        *args,
        cancel_event: asyncio.Event,
        **kwargs,
    ) -> Any:
        """Run the task, checking for cancellation."""
        if asyncio.iscoroutinefunction(task_fn):
            task = asyncio.create_task(task_fn(*args, **kwargs))

            async def _cancel_watcher():
                await cancel_event.wait()
                task.cancel()

            watcher = asyncio.create_task(_cancel_watcher())
            try:
                result = await task
                return result
            finally:
                watcher.cancel()
        else:
            return task_fn(*args, **kwargs)

    async def cancel(self, task_id: str) -> bool:
        """Cancel a running task by ID."""
        event = self._cancel_events.get(task_id)
        if event:
            event.set()
            return True
        return False

    async def cancel_all(self) -> None:
        """Cancel all running tasks."""
        for event in self._cancel_events.values():
            event.set()
        self._cancel_events.clear()
