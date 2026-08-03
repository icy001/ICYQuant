"""
Logging diagnostics.

Provides runtime diagnostics and
snapshots for the logging platform,
enabling operational visibility into
queue depth, worker status, handler
health, and performance metrics.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .metrics import LoggingMetrics
from .pipeline import LoggingPipeline


class LoggingDiagnostics:
    """
    Logging diagnostics provider.

    Collects runtime diagnostics from
    the logging pipeline, providing a
    single snapshot for monitoring and
    debugging.

    Usage:
        diagnostics = LoggingDiagnostics(
            pipeline=pipeline,
            metrics=metrics,
        )
        snapshot = await diagnostics.snapshot()
    """

    def __init__(
        self,
        pipeline: Optional[LoggingPipeline] = None,
        metrics: Optional[LoggingMetrics] = None,
    ) -> None:
        """
        Initialize diagnostics.

        Args:
            pipeline: LoggingPipeline to diagnose.
            metrics: LoggingMetrics to report.
        """

        self._pipeline = pipeline
        self._metrics = metrics

    async def snapshot(
        self,
    ) -> Dict[str, Any]:
        """
        Get a diagnostics snapshot.

        Returns:
            Diagnostics dictionary with:
            - queue_size: Current queue depth
            - buffer_size: Current buffer depth
            - worker_running: Worker status
            - handlers: Number of handlers
            - dropped_logs: Total dropped
            - flush_latency_ms: Last flush latency
            - batch_count: Total batches
            - avg_batch_size: Average batch size
        """

        if self._pipeline is None:
            return self._empty_snapshot()

        status = self._pipeline.get_status()

        return {
            "queue_size": status["queue"]["size"],
            "queue_max": status["queue"]["max_size"],
            "queue_policy": status["queue"]["policy"],
            "buffer_size": status["buffer"]["size"],
            "buffer_capacity": status["buffer"]["capacity"],
            "worker_running": status["worker"]["running"],
            "worker_cycles": status["worker"]["cycle_count"],
            "worker_errors": status["worker"]["error_count"],
            "handlers": status["handlers"],
            "handler_count": status["dispatcher"]["handler_count"],
            "dispatch_count": status["dispatcher"]["dispatch_count"],
            "dropped_logs": status["queue"]["dropped"],
            "dropped_buffer": status["buffer"]["total_dropped"],
            "flush_latency_ms": round(
                status["metrics"]["flush_latency_ms"], 2
            ),
            "avg_flush_latency_ms": round(
                status["metrics"]["avg_flush_latency_ms"], 2
            ),
            "batch_count": status["metrics"]["batch_count"],
            "avg_batch_size": status["collector"]["avg_batch_size"],
            "queued_total": status["metrics"]["queued_logs"],
            "flushed_total": status["metrics"]["flushed_logs"],
            "drop_rate": status["metrics"]["drop_rate"],
            "pipeline_started": status["started"],
        }

    def _empty_snapshot(
        self,
    ) -> Dict[str, Any]:
        """Get empty snapshot when pipeline is not available."""

        if self._metrics is not None:
            m = self._metrics.to_dict()
            return {
                "queue_size": m["queue_size"],
                "buffer_size": m["buffer_size"],
                "worker_running": False,
                "handlers": 0,
                "dropped_logs": m["dropped_logs"],
                "flush_latency_ms": m["flush_latency_ms"],
                "batch_count": m["batch_count"],
                "drop_rate": m["drop_rate"],
            }

        return {
            "queue_size": 0,
            "worker_running": False,
            "handlers": 0,
            "dropped_logs": 0,
            "flush_latency_ms": 0.0,
        }

    async def health_check(
        self,
    ) -> Dict[str, Any]:
        """
        Run health check.

        Returns:
            Health status dictionary.
        """

        snap = await self.snapshot()

        healthy = (
            snap.get("pipeline_started", False)
            and snap.get("worker_running", False)
            and snap.get("drop_rate", 1.0) < 0.1
        )

        return {
            "healthy": healthy,
            "queue_size": snap.get("queue_size", 0),
            "worker_running": snap.get("worker_running", False),
            "drop_rate": snap.get("drop_rate", 0.0),
            "handlers": snap.get("handlers", 0),
            "flush_latency_ms": snap.get("flush_latency_ms", 0.0),
        }
