"""
Task scheduler auto-instrumentation.

Provides automatic span creation for
the ICYQuant task scheduler, including:
- Cron trigger tracking
- Task execution monitoring
- Failure tracking
- Duration measurement
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

from .base import Instrumentation


class SchedulerInstrumentation(Instrumentation):
    """
    Task scheduler auto-instrumentation.

    Wraps the task scheduler to automatically
    create spans for cron triggers, task
    execution, and scheduling events.

    Features:
    - Cron trigger span creation
    - Task execution tracking
    - Failure and retry tracking
    - Duration measurement
    - Task result capture

    Usage:
        instr = SchedulerInstrumentation()
        await instr.install()

        # When scheduler triggers a task:
        scheduler.schedule(my_task, cron="*/5 * * * *")
        # Execution automatically traced
    """

    name: str = "scheduler"
    version: str = "1.0"

    def __init__(
        self,
        tracer: Optional[Any] = None,
        capture_result: bool = False,
    ) -> None:
        """
        Initialize scheduler instrumentation.

        Args:
            tracer: Optional Tracer instance.
            capture_result: Whether to capture task results.
        """

        super().__init__(tracer=tracer)
        self._capture_result = capture_result
        self._installed: bool = False
        self._trigger_count: int = 0
        self._success_count: int = 0
        self._failure_count: int = 0

    @property
    def is_instrumented(
        self,
    ) -> bool:
        return self._installed

    @property
    def stats(
        self,
    ) -> Dict[str, int]:
        """Get scheduler statistics."""
        return {
            "triggers": self._trigger_count,
            "successes": self._success_count,
            "failures": self._failure_count,
        }

    async def install(
        self,
    ) -> None:
        """Install scheduler instrumentation."""
        self._installed = True

    async def uninstall(
        self,
    ) -> None:
        """Remove scheduler instrumentation."""
        self._installed = False

    def create_trigger_span(
        self,
        task_name: str,
        cron_expression: Optional[str] = None,
        task_id: Optional[str] = None,
    ) -> Any:
        """
        Create a cron trigger span.

        Args:
            task_name: Task function name.
            cron_expression: Cron expression.
            task_id: Task identifier.

        Returns:
            SpanModel instance.
        """

        from ...models import SpanKind

        span = self.tracer.start_span(
            operation=f"scheduler.trigger.{task_name}",
            kind=SpanKind.INTERNAL,
        )

        span.add_attribute("icyquant.scheduler.task", task_name)
        span.add_attribute("icyquant.scheduler.operation", "trigger")

        if cron_expression:
            span.add_attribute("icyquant.scheduler.cron", cron_expression)

        if task_id:
            span.add_attribute("icyquant.scheduler.task_id", task_id)

        self._trigger_count += 1
        return span

    def create_execution_span(
        self,
        task_name: str,
        task_id: Optional[str] = None,
        retry_count: int = 0,
    ) -> Any:
        """
        Create a task execution span.

        Args:
            task_name: Task function name.
            task_id: Task identifier.
            retry_count: Number of retries.

        Returns:
            SpanModel instance.
        """

        from ...models import SpanKind

        span = self.tracer.start_span(
            operation=f"scheduler.execute.{task_name}",
            kind=SpanKind.INTERNAL,
        )

        span.add_attribute("icyquant.scheduler.task", task_name)
        span.add_attribute("icyquant.scheduler.operation", "execute")

        if task_id:
            span.add_attribute("icyquant.scheduler.task_id", task_id)

        if retry_count > 0:
            span.add_attribute("icyquant.retry.count", retry_count)

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
                "icyquant.scheduler.result",
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
