"""
Runtime metrics collectors.

Collects Python runtime, AsyncIO event loop,
and process-level metrics for the monitoring
infrastructure.
"""

from __future__ import annotations

import asyncio
import gc
import os
import platform
from typing import Any, Dict, List, Optional

from .collector import BaseCollector
from .models import MetricPoint


class RuntimeCollector(BaseCollector):
    """
    Python runtime metrics collector.

    Collects metrics about the Python
    runtime environment including GC,
    memory, and process information.

    Metrics:
    - icyquant_python_gc_total: GC collections
    - icyquant_process_memory_rss_bytes: RSS memory
    - icyquant_process_cpu_seconds_total: CPU time
    - icyquant_process_open_fds: Open file descriptors
    - icyquant_python_objects_total: Live objects
    """

    def __init__(
        self,
        namespace: str = "icyquant",
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Initialize runtime collector.

        Args:
            namespace: Metric namespace prefix.
            labels: Default labels.
        """

        super().__init__(
            name="runtime",
            namespace=namespace,
            labels=labels,
        )
        self._prev_gc_counts = gc.get_count()

    async def collect(
        self,
    ) -> List[MetricPoint]:
        """
        Collect Python runtime metrics.

        Returns:
            List of MetricPoint objects.
        """

        points: List[MetricPoint] = []

        # GC counts
        gc_counts = gc.get_count()
        gc_total = sum(gc_counts)
        points.append(
            self._make_point(
                "python_gc_total",
                float(gc_total),
                metric_type="counter",
                unit="",
            )
        )

        # Objects count
        points.append(
            self._make_point(
                "python_objects_total",
                float(len(gc.get_objects())),
                metric_type="gauge",
                unit="",
            )
        )

        # Process memory (best-effort)
        try:
            import resource

            usage = resource.getrusage(
                resource.RUSAGE_SELF
            )
            max_rss = usage.ru_maxrss * 1024  # KB to bytes
            points.append(
                self._make_point(
                    "process_memory_rss_bytes",
                    float(max_rss),
                    metric_type="gauge",
                    unit="bytes",
                )
            )

            # CPU time
            cpu_time = (
                usage.ru_utime + usage.ru_stime
            )
            points.append(
                self._make_point(
                    "process_cpu_seconds_total",
                    float(cpu_time),
                    metric_type="counter",
                    unit="seconds",
                )
            )
        except (ImportError, AttributeError):
            # resource module may not be available
            # on all platforms (e.g., some Windows)
            pass

        # PID
        points.append(
            self._make_point(
                "process_pid",
                float(os.getpid()),
                metric_type="gauge",
                unit="",
            )
        )

        return points


class AsyncIOCollector(BaseCollector):
    """
    AsyncIO event loop metrics collector.

    Collects metrics about the asyncio event
    loop including task counts, coroutine
    counts, and loop lag.

    Metrics:
    - icyquant_async_tasks: Pending tasks
    - icyquant_async_coroutines: Pending coroutines
    - icyquant_async_callbacks: Scheduled callbacks
    """

    def __init__(
        self,
        namespace: str = "icyquant",
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        """
        Initialize AsyncIO collector.

        Args:
            namespace: Metric namespace prefix.
            labels: Default labels.
        """

        super().__init__(
            name="asyncio",
            namespace=namespace,
            labels=labels,
        )
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def set_loop(
        self,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        """
        Set the event loop to monitor.

        Args:
            loop: AsyncIO event loop.
        """

        self._loop = loop

    async def collect(
        self,
    ) -> List[MetricPoint]:
        """
        Collect AsyncIO event loop metrics.

        Returns:
            List of MetricPoint objects.
        """

        points: List[MetricPoint] = []

        try:
            loop = self._loop
            if loop is None:
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = asyncio.get_event_loop()

            if loop is not None:
                # Task count
                try:
                    tasks = len(
                        asyncio.all_tasks(loop)
                    )
                except (TypeError, RuntimeError):
                    tasks = 0

                points.append(
                    self._make_point(
                        "async_tasks",
                        float(tasks),
                        metric_type="gauge",
                        unit="",
                    )
                )

                # Coroutine count
                try:
                    coros = len(
                        asyncio.all_tasks(loop)
                    )
                except (TypeError, RuntimeError):
                    coros = 0

                points.append(
                    self._make_point(
                        "async_coroutines",
                        float(coros),
                        metric_type="gauge",
                        unit="",
                    )
                )

                # Scheduled callbacks
                try:
                    callbacks = len(
                        loop._scheduled
                    )  # type: ignore
                except (AttributeError, TypeError):
                    callbacks = 0

                points.append(
                    self._make_point(
                        "async_callbacks",
                        float(callbacks),
                        metric_type="gauge",
                        unit="",
                    )
                )

        except Exception:
            pass

        return points
