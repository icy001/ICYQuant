"""
Logging metrics.

Tracks key metrics for the async logging
pipeline, providing visibility into
queue depth, flush rates, and latency.

Metrics can be registered with the
Monitoring Registry for Prometheus
export and alerting.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional


@dataclass
class LoggingMetrics:
    """
    Logging pipeline metrics.

    Tracks throughput, latency, and error
    metrics for the async logging pipeline.

    Attributes:
        queued_logs: Total logs queued.
        flushed_logs: Total logs flushed to handlers.
        dropped_logs: Total logs dropped due to backpressure.
        batch_count: Total batches processed.
        flush_latency_ms: Last flush latency in milliseconds.
        total_flush_time_ms: Total time spent flushing.
        queue_size: Current queue size.
        buffer_size: Current buffer size.
    """

    queued_logs: int = 0
    flushed_logs: int = 0
    dropped_logs: int = 0
    batch_count: int = 0
    flush_latency_ms: float = 0.0
    total_flush_time_ms: float = 0.0
    queue_size: int = 0
    buffer_size: int = 0

    @property
    def avg_flush_latency_ms(
        self,
    ) -> float:
        """Get average flush latency."""

        if self.batch_count == 0:
            return 0.0
        return self.total_flush_time_ms / self.batch_count

    @property
    def drop_rate(
        self,
    ) -> float:
        """Get drop rate."""

        total = self.queued_logs + self.dropped_logs
        if total == 0:
            return 0.0
        return self.dropped_logs / total

    @property
    def flush_rate(
        self,
    ) -> float:
        """Get flush rate (flushed/queued)."""

        if self.queued_logs == 0:
            return 0.0
        return self.flushed_logs / self.queued_logs

    def record_queued(
        self,
        count: int = 1,
    ) -> None:
        """Record queued logs."""

        self.queued_logs += count

    def record_flushed(
        self,
        count: int,
        latency_ms: float,
    ) -> None:
        """Record flushed logs."""

        self.flushed_logs += count
        self.batch_count += 1
        self.flush_latency_ms = latency_ms
        self.total_flush_time_ms += latency_ms

    def record_dropped(
        self,
        count: int = 1,
    ) -> None:
        """Record dropped logs."""

        self.dropped_logs += count

    def update_queue_size(
        self,
        size: int,
    ) -> None:
        """Update queue size."""

        self.queue_size = size

    def update_buffer_size(
        self,
        size: int,
    ) -> None:
        """Update buffer size."""

        self.buffer_size = size

    def to_dict(
        self,
    ) -> dict:
        """
        Convert to dictionary.

        Returns:
            Dictionary representation.
        """

        return {
            "queued_logs": self.queued_logs,
            "flushed_logs": self.flushed_logs,
            "dropped_logs": self.dropped_logs,
            "batch_count": self.batch_count,
            "flush_latency_ms": round(self.flush_latency_ms, 2),
            "avg_flush_latency_ms": round(self.avg_flush_latency_ms, 2),
            "total_flush_time_ms": round(self.total_flush_time_ms, 2),
            "queue_size": self.queue_size,
            "buffer_size": self.buffer_size,
            "drop_rate": round(self.drop_rate, 4),
            "flush_rate": round(self.flush_rate, 4),
        }

    def reset(
        self,
    ) -> None:
        """Reset all metrics."""

        self.queued_logs = 0
        self.flushed_logs = 0
        self.dropped_logs = 0
        self.batch_count = 0
        self.flush_latency_ms = 0.0
        self.total_flush_time_ms = 0.0
        self.queue_size = 0
        self.buffer_size = 0
