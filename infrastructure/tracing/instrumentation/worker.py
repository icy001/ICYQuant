"""
Background worker auto-instrumentation.

Provides automatic span creation for
ICYQuant background worker operations, including:
- Worker start/stop events
- Task execution tracking
- Retry tracking
- Failure handling
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .base import Instrumentation


class WorkerInstrumentation(Instrumentation):
    """
    Background worker auto-instrumentation.

    Wraps background workers to automatically
    create spans for task execution, retry,
    and failure events.

    Features:
    - Worker lifecycle spans (start/stop)
    - Task execution tracking
    - Retry and failure tracking
    - Queue monitoring
    - Duration measurement

    Usage:
        instr = WorkerInstrumentation()
        await instr.install()

        # When worker processes a task:
        worker.submit(my_background_task)
        # Task execution automatically traced
    """

    name: str = "worker"
    version: str = "1.0"

    def __init__(
        self,
        tracer: Optional[Any] = None,
        worker_name: str = "default",
        capture_result: bool = False,
    ) -> None:
        """
        Initialize worker instrumentation.

        Args:
            tracer: Optional Tracer instance.
            worker_name: Worker name for span identification.
            capture_result: Whether to capture task results.
        """

        super().__init__(tracer=tracer)
        self._worker_name = worker_name
        self._capture_result = capture_result
        self._installed: bool = False
        self._task_count: int = 0
        self._success_count: int = 0
        self._failure_count: int = 0
        self._retry_count: int = 0

    @property
    def is_instrumented(
        self,
    ) -> bool:
        return self._installed

    @property
    def stats(
        self,
    ) -> Dict[str, int]:
        """Get worker statistics."""
        return {
            "worker": self._worker_name,
            "tasks": self._task_count,
            "successes": self._success_count,
            "failures": self._failure_count,
            "retries": self._retry_count,
        }

    async def install(
        self,
    ) -> None:
        """Install worker instrumentation."""
        self._installed = True

    async def uninstall(
        self,
    ) -> None:
        """Remove worker instrumentation."""
        self._installed = False

    def create_worker_span(
        self,
        operation: str = "start",
    ) -> Any:
        """
        Create a worker lifecycle span.

        Args:
            operation: Lifecycle operation (start, stop).

        Returns:
            SpanModel instance.
        """

        from ...models import SpanKind

        span = self.tracer.start_span(
            operation=f"worker.{operation}",
            kind=SpanKind.INTERNAL,
        )

        span.add_attribute("icyquant.worker.name", self._worker_name)
        span.add_attribute("icyquant.worker.operation", operation)

        return span

    def create_task_span(
        self,
        task_name: str,
        task_id: Optional[str] = None,
        queue: Optional[str] = None,
        retry_count: int = 0,
        priority: Optional[int] = None,
    ) -> Any:
        """
        Create a task execution span.

        Args:
            task_name: Task function name.
            task_id: Task identifier.
            queue: Source queue name.
            retry_count: Number of retries.
            priority: Task priority.

        Returns:
            SpanModel instance.
        """

        from ...models import SpanKind

        span = self.tracer.start_span(
            operation=f"worker.execute.{task_name}",
            kind=SpanKind.CONSUMER,
        )

        span.add_attribute("icyquant.worker.name", self._worker_name)
        span.add_attribute("icyquant.worker.operation", "execute")
        span.add_attribute("icyquant.worker.task", task_name)

        if task_id:
            span.add_attribute("icyquant.worker.task_id", task_id)

        if queue:
            span.add_attribute("icyquant.worker.queue", queue)

        if retry_count > 0:
            span.add_attribute("icyquant.retry.count", retry_count)
            self._retry_count += 1

        if priority is not None:
            span.add_attribute("icyquant.worker.priority", priority)

        self._task_count += 1
        return span

    def record_success(
        self,
        span: Any,
        result: Optional[Any] = None,
    ) -> None:
        """
        Record task success.

        Args:
            span: Task span.
            result: Task result.
        """

        from ...models import SpanStatus

        span.set_status(SpanStatus.OK)

        if result and self._capture_result:
            span.add_attribute(
                "icyquant.worker.result",
                str(result)[:256],
            )

        self._success_count += 1

    def record_failure(
        self,
        span: Any,
        error: Exception,
    ) -> None:
        """
        Record task failure.

        Args:
            span: Task span.
            error: Exception that occurred.
        """

        from ...models import SpanStatus

        span.set_status(SpanStatus.ERROR)
        span.add_attribute("exception.type", type(error).__name__)
        span.add_attribute("exception.message", str(error))

        self._failure_count += 1
