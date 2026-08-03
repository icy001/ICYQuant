"""
Trace diagnostics.

Provides diagnostic snapshots of the
tracing pipeline, including queue depth,
buffer status, exporter health, and latency.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .metrics import TraceMetrics


class TraceDiagnostics:
    """
    Trace pipeline diagnostics.

    Provides a unified snapshot of the
    tracing pipeline health, combining
    metrics from all pipeline components.

    Usage:
        diagnostics = TraceDiagnostics(
            metrics=metrics,
            queue=queue,
            buffer=buffer,
            exporters=export_manager,
        )
        snapshot = await diagnostics.snapshot()
    """

    def __init__(
        self,
        metrics: Optional[TraceMetrics] = None,
        queue: Optional[Any] = None,
        buffer: Optional[Any] = None,
        exporters: Optional[Any] = None,
        retry: Optional[Any] = None,
    ) -> None:
        self._metrics = metrics or TraceMetrics()
        self._queue = queue
        self._buffer = buffer
        self._exporters = exporters
        self._retry = retry

    async def snapshot(self) -> Dict[str, Any]:
        """
        Get a diagnostic snapshot.

        Returns:
            Dictionary with diagnostic information.
        """

        result: Dict[str, Any] = {
            "queue": 0,
            "buffer": 0,
            "retry": 0,
            "exporters": 0,
            "latency_ms": 0,
        }

        if self._queue is not None:
            stats = self._queue.get_stats()
            result["queue"] = stats.get("size", 0)

        if self._buffer is not None:
            stats = self._buffer.get_stats()
            result["buffer"] = stats.get("memory_size", 0) + stats.get("disk_count", 0)

        if self._retry is not None:
            stats = self._retry.get_stats()
            result["retry"] = stats.get("retry_count", 0)

        if self._exporters is not None:
            stats = self._exporters.get_stats()
            result["exporters"] = stats.get("exporter_count", 0)

        result["latency_ms"] = self._metrics.export_latency_ms
        result["metrics"] = self._metrics.get_stats()

        return result

    async def health_check(self) -> Dict[str, Any]:
        """
        Run a health check.

        Returns:
            Health status dictionary.
        """

        snapshot = await self.snapshot()
        metrics = snapshot.get("metrics", {})

        healthy = True
        issues = []

        if metrics.get("failure_rate", 0) > 0.5:
            healthy = False
            issues.append("high_failure_rate")

        if metrics.get("dropped_spans", 0) > 1000:
            healthy = False
            issues.append("high_drop_count")

        if snapshot.get("queue", 0) > 1800:
            healthy = False
            issues.append("queue_near_full")

        return {
            "healthy": healthy,
            "issues": issues,
            "snapshot": snapshot,
        }
