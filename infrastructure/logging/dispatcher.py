"""
Log dispatcher.

Dispatches batches of log records to
all registered handlers, providing
error isolation between handlers.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, List

from .handlers import LogHandler
from .metrics import LoggingMetrics
from .models import LogEntry


class LogDispatcher:
    """
    Log record dispatcher.

    Sends batches of log records to all
    registered handlers. Each handler
    receives the full batch, enabling
    batch-optimized processing (e.g. bulk
    Elasticsearch indexing).

    Features:
    - Error isolation (one handler failure doesn't affect others)
    - Concurrent dispatch to multiple handlers
    - Flush latency tracking
    - Metrics integration

    Usage:
        dispatcher = LogDispatcher(
            handlers=[console_handler, file_handler],
        )
        await dispatcher.dispatch(batch)
    """

    def __init__(
        self,
        handlers: List[LogHandler] = None,
        metrics: Any = None,
        continue_on_error: bool = True,
    ) -> None:
        """
        Initialize dispatcher.

        Args:
            handlers: List of LogHandler instances.
            metrics: Optional LoggingMetrics for tracking.
            continue_on_error: Whether to continue on handler errors.
        """

        self._handlers: List[LogHandler] = handlers or []
        self._metrics: Any = metrics
        self._continue_on_error = continue_on_error
        self._dispatch_count: int = 0
        self._error_count: int = 0
        self._total_records: int = 0

    @property
    def handlers(
        self,
    ) -> List[LogHandler]:
        """Get registered handlers."""
        return self._handlers

    @property
    def dispatch_count(
        self,
    ) -> int:
        """Get total dispatch count."""
        return self._dispatch_count

    @property
    def error_count(
        self,
    ) -> int:
        """Get total error count."""
        return self._error_count

    @property
    def total_records(
        self,
    ) -> int:
        """Get total records dispatched."""
        return self._total_records

    def add_handler(
        self,
        handler: LogHandler,
    ) -> None:
        """
        Add a handler.

        Args:
            handler: Handler to add.
        """

        self._handlers.append(handler)

    def remove_handler(
        self,
        handler: LogHandler,
    ) -> None:
        """
        Remove a handler.

        Args:
            handler: Handler to remove.
        """

        self._handlers.remove(handler)

    async def dispatch(
        self,
        batch: List[LogEntry],
    ) -> None:
        """
        Dispatch a batch of records to all handlers.

        Each handler receives the entire batch.
        Handlers are invoked concurrently for
        maximum throughput.

        Args:
            batch: List of LogEntry records to dispatch.
        """

        if not batch:
            return

        start_time = time.time()
        self._dispatch_count += 1
        self._total_records += len(batch)

        # Dispatch to each handler concurrently
        tasks = [
            self._dispatch_to_handler(handler, batch)
            for handler in self._handlers
        ]
        await asyncio.gather(*tasks, return_exceptions=True)

        # Track metrics
        latency_ms = (time.time() - start_time) * 1000
        if self._metrics is not None:
            self._metrics.flushed_logs += len(batch)
            self._metrics.batch_count += 1
            self._metrics.flush_latency_ms = latency_ms

    async def _dispatch_to_handler(
        self,
        handler: LogHandler,
        batch: List[LogEntry],
    ) -> None:
        """
        Dispatch batch to a single handler.

        Args:
            handler: Target handler.
            batch: Records to dispatch.
        """

        try:
            for record in batch:
                result = handler.emit(record)
                if asyncio.iscoroutine(result):
                    await result
        except Exception:
            self._error_count += 1
            if not self._continue_on_error:
                raise

    def get_stats(
        self,
    ) -> dict:
        """
        Get dispatcher statistics.

        Returns:
            Statistics dictionary.
        """

        return {
            "handler_count": len(self._handlers),
            "dispatch_count": self._dispatch_count,
            "total_records": self._total_records,
            "error_count": self._error_count,
        }
