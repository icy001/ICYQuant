"""
Trace metrics.

Tracks metrics about the trace export pipeline,
including export counts, success/failure rates,
retry counts, and latency measurements.

Prometheus metrics:
- icyquant_trace_export_total
- icyquant_trace_success_total
- icyquant_trace_failure_total
- icyquant_trace_retry_total
- icyquant_trace_queue_size
- icyquant_trace_export_latency_seconds
"""

from __future__ import annotations

from typing import Any, Dict


class TraceMetrics:
    """
    Trace pipeline metrics.

    Tracks operational metrics for the trace
    export pipeline, providing visibility into
    export health and performance.

    Usage:
        metrics = TraceMetrics()
        metrics.record_span()
        metrics.record_export(success=True, latency_ms=8.5)
        stats = metrics.get_stats()
    """

    def __init__(self) -> None:
        self.export_total: int = 0
        self.export_success: int = 0
        self.export_failed: int = 0
        self.retry_total: int = 0
        self.dropped_spans: int = 0
        self.export_latency_ms: float = 0.0
        self._total_latency: float = 0.0
        self._span_count: int = 0

    def record_span(self) -> None:
        """Record a span entering the pipeline."""
        self._span_count += 1

    def record_export(
        self,
        success: bool = True,
        latency_ms: float = 0.0,
    ) -> None:
        """Record an export operation."""
        self.export_total += 1
        if success:
            self.export_success += 1
        else:
            self.export_failed += 1
        self._total_latency += latency_ms
        self.export_latency_ms = latency_ms

    def record_retry(self) -> None:
        """Record a retry attempt."""
        self.retry_total += 1

    def record_dropped(self, count: int = 1) -> None:
        """Record dropped spans."""
        self.dropped_spans += count

    @property
    def avg_latency_ms(self) -> float:
        """Get average export latency."""
        if self.export_total == 0:
            return 0.0
        return self._total_latency / self.export_total

    @property
    def success_rate(self) -> float:
        """Get export success rate."""
        if self.export_total == 0:
            return 1.0
        return self.export_success / self.export_total

    @property
    def failure_rate(self) -> float:
        """Get export failure rate."""
        if self.export_total == 0:
            return 0.0
        return self.export_failed / self.export_total

    def get_stats(self) -> Dict[str, Any]:
        """Get all metrics."""
        return {
            "export_total": self.export_total,
            "export_success": self.export_success,
            "export_failed": self.export_failed,
            "retry_total": self.retry_total,
            "dropped_spans": self.dropped_spans,
            "span_count": self._span_count,
            "export_latency_ms": round(self.export_latency_ms, 2),
            "avg_latency_ms": round(self.avg_latency_ms, 2),
            "success_rate": round(self.success_rate, 4),
            "failure_rate": round(self.failure_rate, 4),
        }

    def get_prometheus_metrics(self) -> str:
        """Get metrics in Prometheus text format."""
        lines = [
            f"icyquant_trace_export_total {self.export_total}",
            f"icyquant_trace_success_total {self.export_success}",
            f"icyquant_trace_failure_total {self.export_failed}",
            f"icyquant_trace_retry_total {self.retry_total}",
            f"icyquant_trace_dropped_spans {self.dropped_spans}",
            f"icyquant_trace_export_latency_seconds {self.export_latency_ms / 1000:.6f}",
            f"icyquant_trace_avg_latency_seconds {self.avg_latency_ms / 1000:.6f}",
        ]
        return "\n".join(lines)

    def reset(self) -> None:
        """Reset all metrics."""
        self.export_total = 0
        self.export_success = 0
        self.export_failed = 0
        self.retry_total = 0
        self.dropped_spans = 0
        self.export_latency_ms = 0.0
        self._total_latency = 0.0
        self._span_count = 0
