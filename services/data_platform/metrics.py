"""
ICYQuant Data Platform Metrics — Prometheus metrics for unified data platform.

Tracks data requests, dataset access, catalog queries, governance checks,
pipeline latency, replay requests, and API latency.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class MetricSnapshot:
    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class DataPlatformMetrics:
    """Prometheus-compatible metrics for the data platform.

    Metrics:
        icyquant_data_requests_total      — Total data requests
        icyquant_dataset_access_total     — Total dataset accesses
        icyquant_catalog_queries_total    — Total catalog queries
        icyquant_governance_checks_total  — Total governance checks
        icyquant_data_pipeline_latency    — Pipeline execution latency (ms)
        icyquant_replay_requests_total    — Total replay requests
        icyquant_data_api_latency         — API endpoint latency (ms)
        icyquant_data_stream_throughput   — Streaming throughput (msgs/sec)
        icyquant_data_lake_storage_bytes  — Data lake storage usage
    """

    def __init__(self) -> None:
        self._counters: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._gauges: dict[str, float] = {}
        self._start_time = time.time()

    # ── Counters ──

    def increment_data_requests(self, count: int = 1) -> None:
        key = "icyquant_data_requests_total"
        self._counters[key] = self._counters.get(key, 0) + count

    def increment_dataset_access(self, dataset: str = "") -> None:
        key = "icyquant_dataset_access_total"
        self._counters[key] = self._counters.get(key, 0) + 1

    def increment_catalog_queries(self) -> None:
        key = "icyquant_catalog_queries_total"
        self._counters[key] = self._counters.get(key, 0) + 1

    def increment_governance_checks(self) -> None:
        key = "icyquant_governance_checks_total"
        self._counters[key] = self._counters.get(key, 0) + 1

    def increment_replay_requests(self) -> None:
        key = "icyquant_replay_requests_total"
        self._counters[key] = self._counters.get(key, 0) + 1

    # ── Histograms ──

    def record_pipeline_latency(self, latency_ms: float) -> None:
        key = "icyquant_data_pipeline_latency"
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(latency_ms)

    def record_api_latency(self, latency_ms: float, endpoint: str = "") -> None:
        key = "icyquant_data_api_latency"
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(latency_ms)

    # ── Gauges ──

    def set_stream_throughput(self, msgs_per_sec: float) -> None:
        self._gauges["icyquant_data_stream_throughput"] = msgs_per_sec

    def set_storage_bytes(self, bytes_used: int) -> None:
        self._gauges["icyquant_data_lake_storage_bytes"] = float(bytes_used)

    def set_active_connections(self, count: int) -> None:
        self._gauges["icyquant_data_active_connections"] = float(count)

    # ── Export ──

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines: list[str] = []

        for name, value in self._counters.items():
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")

        for name, value in self._gauges.items():
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")

        for name, values in self._histograms.items():
            if values:
                lines.append(f"# TYPE {name} histogram")
                lines.append(f"{name}_sum {sum(values)}")
                lines.append(f"{name}_count {len(values)}")
                avg = sum(values) / len(values)
                lines.append(f"{name}_avg {avg:.2f}")

        return "\n".join(lines)

    def get_snapshot(self) -> dict[str, Any]:
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                name: {"count": len(vals), "sum": sum(vals), "avg": sum(vals) / len(vals) if vals else 0}
                for name, vals in self._histograms.items()
            },
            "uptime_seconds": time.time() - self._start_time,
        }

    @property
    def total_requests(self) -> int:
        return int(self._counters.get("icyquant_data_requests_total", 0))

    @property
    def total_catalog_queries(self) -> int:
        return int(self._counters.get("icyquant_catalog_queries_total", 0))
