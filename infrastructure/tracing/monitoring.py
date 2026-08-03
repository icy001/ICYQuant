"""
Tracing monitoring.

Collects operational metrics from the tracing
platform, exposing them through the unified
Monitoring Registry for Prometheus scraping.

Metrics Collected:
- icyquant_trace_active_total: Active trace count
- icyquant_span_active_total: Active span count
- icyquant_trace_export_queue: Export queue depth
- icyquant_sampling_ratio: Current sampling ratio
- icyquant_processor_latency_seconds: Processor latency
- icyquant_export_failure_total: Total export failures

Integration:
    TracingService
        |
        v
    TracingMonitoring
        |
        v
    Monitoring Registry
        |
        v
    Prometheus Exporter
        |
        v
    Grafana Dashboard

Usage:
    monitoring = TracingMonitoring(
        registry=trace_registry,
        metrics=trace_metrics,
        export_manager=export_manager,
    )
    metrics = await monitoring.collect()
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .exporters import ExportManager
from .metrics import TraceMetrics
from .registry import TraceRegistry


class TracingMonitoring:
    """
    Tracing metrics collector.

    Collects metrics from the tracing platform
    components (registry, metrics, exporters)
    and exposes them in a unified format for
    the Monitoring Layer.

    Features:
    - Active trace/span tracking
    - Export queue depth monitoring
    - Sampling ratio reporting
    - Processor latency measurement
    - Export failure tracking
    - Prometheus text format export

    Usage:
        monitoring = TracingMonitoring(
            registry=registry,
            metrics=metrics,
            export_manager=export_manager,
        )
        snapshot = await monitoring.collect()
        prom_text = monitoring.export_prometheus()
    """

    def __init__(
        self,
        registry: Optional[TraceRegistry] = None,
        metrics: Optional[TraceMetrics] = None,
        export_manager: Optional[ExportManager] = None,
        sampler: Optional[Any] = None,
    ) -> None:
        """
        Initialize monitoring collector.

        Args:
            registry: TraceRegistry for trace/span counts.
            metrics: TraceMetrics for export metrics.
            export_manager: ExportManager for exporter stats.
            sampler: Optional sampler for sampling ratio.
        """

        self._registry = registry
        self._metrics = metrics or TraceMetrics()
        self._export_manager = export_manager
        self._sampler = sampler

        self._collect_count: int = 0

    @property
    def collect_count(
        self,
    ) -> int:
        """Get total collect count."""
        return self._collect_count

    async def collect(
        self,
    ) -> Dict[str, Any]:
        """
        Collect tracing metrics.

        Gathers metrics from all tracing
        components into a unified snapshot.

        Returns:
            Metrics dictionary with all tracing metrics.
        """

        self._collect_count += 1

        # Registry stats
        active_traces = 0
        finished_traces = 0
        total_spans = 0
        if self._registry is not None:
            stats = self._registry.get_stats()
            active_traces = stats.get("active", 0)
            finished_traces = stats.get("finished", 0)
            total_spans = stats.get("spans", 0)

        # Export stats
        exporter_count = 0
        if self._export_manager is not None:
            export_stats = self._export_manager.get_stats()
            exporter_count = export_stats.get("exporter_count", 0)

        # Pipeline metrics
        metrics_stats = self._metrics.get_stats()

        # Sampling ratio
        sample_ratio = 1.0
        if self._sampler is not None and hasattr(
            self._sampler, "ratio"
        ):
            sample_ratio = getattr(
                self._sampler, "ratio", 1.0
            )

        return {
            "active_traces": active_traces,
            "finished_traces": finished_traces,
            "total_spans": total_spans,
            "exporter_count": exporter_count,
            "sample_ratio": sample_ratio,
            "export_total": metrics_stats.get(
                "export_total", 0
            ),
            "export_success": metrics_stats.get(
                "export_success", 0
            ),
            "export_failed": metrics_stats.get(
                "export_failed", 0
            ),
            "export_latency_ms": metrics_stats.get(
                "export_latency_ms", 0.0
            ),
            "avg_latency_ms": metrics_stats.get(
                "avg_latency_ms", 0.0
            ),
            "success_rate": metrics_stats.get(
                "success_rate", 1.0
            ),
            "dropped_spans": metrics_stats.get(
                "dropped_spans", 0
            ),
            "collect_count": self._collect_count,
        }

    def export_prometheus(
        self,
    ) -> str:
        """
        Export metrics in Prometheus text format.

        Returns:
            Prometheus exposition format string.
        """

        # Collect synchronously (uses cached values)
        metrics_stats = self._metrics.get_stats()

        active_traces = 0
        total_spans = 0
        if self._registry is not None:
            stats = self._registry.get_stats()
            active_traces = stats.get("active", 0)
            total_spans = stats.get("spans", 0)

        exporter_count = 0
        if self._export_manager is not None:
            export_stats = self._export_manager.get_stats()
            exporter_count = export_stats.get(
                "exporter_count", 0
            )

        sample_ratio = 1.0
        if self._sampler is not None and hasattr(
            self._sampler, "ratio"
        ):
            sample_ratio = getattr(
                self._sampler, "ratio", 1.0
            )

        lines = [
            f"icyquant_trace_active_total {active_traces}",
            f"icyquant_span_active_total {total_spans}",
            f"icyquant_trace_export_queue {metrics_stats.get('export_total', 0)}",
            f"icyquant_sampling_ratio {sample_ratio}",
            f"icyquant_processor_latency_seconds {metrics_stats.get('export_latency_ms', 0.0) / 1000:.6f}",
            f"icyquant_export_failure_total {metrics_stats.get('export_failed', 0)}",
            f"icyquant_export_success_total {metrics_stats.get('export_success', 0)}",
            f"icyquant_export_dropped_spans_total {metrics_stats.get('dropped_spans', 0)}",
            f"icyquant_exporter_count {exporter_count}",
        ]
        return "\n".join(lines)

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """
        Get monitoring status.

        Returns:
            Status dictionary.
        """

        return {
            "collect_count": self._collect_count,
            "registry": self._registry is not None,
            "metrics": self._metrics is not None,
            "export_manager": self._export_manager is not None,
            "sampler": self._sampler is not None,
        }
