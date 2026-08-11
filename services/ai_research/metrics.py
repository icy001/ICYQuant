"""
ICYQuant AI Research Metrics — Prometheus-compatible metrics for the research platform.

Tracks research requests, pipeline latency, retrieval queries,
hypothesis generation, report generation, experiments, and workspace sessions.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


@dataclass
class MetricSnapshot:
    name: str
    value: float
    labels: dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)


class ResearchMetrics:
    """Prometheus-compatible metrics for the AI Research Platform.

    Metrics:
        icyquant_research_requests_total     — Total research requests
        icyquant_research_pipeline_latency   — Pipeline execution latency (ms)
        icyquant_retrieval_queries_total     — Total retrieval queries
        icyquant_hypothesis_generated_total  — Total hypotheses generated
        icyquant_reports_generated_total     — Total reports generated
        icyquant_experiments_total           — Total experiments tracked
        icyquant_research_workspace_sessions — Active workspace sessions
        icyquant_knowledge_documents_total   — Total indexed documents
        icyquant_citation_total              — Total citations extracted
    """

    def __init__(self) -> None:
        self._counters: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._gauges: dict[str, float] = {}
        self._start_time = time.time()

    def increment_request(self, labels: Optional[dict[str, str]] = None) -> None:
        """Increment research request counter."""
        key = "icyquant_research_requests_total"
        self._counters[key] = self._counters.get(key, 0) + 1

    def record_pipeline_latency(self, latency_ms: float) -> None:
        """Record pipeline execution latency."""
        key = "icyquant_research_pipeline_latency"
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(latency_ms)

    def increment_retrieval_query(self) -> None:
        """Increment retrieval query counter."""
        key = "icyquant_retrieval_queries_total"
        self._counters[key] = self._counters.get(key, 0) + 1

    def increment_hypothesis_generated(self, count: int = 1) -> None:
        """Increment hypothesis generated counter."""
        key = "icyquant_hypothesis_generated_total"
        self._counters[key] = self._counters.get(key, 0) + count

    def increment_report_generated(self) -> None:
        """Increment report generated counter."""
        key = "icyquant_reports_generated_total"
        self._counters[key] = self._counters.get(key, 0) + 1

    def increment_experiment(self) -> None:
        """Increment experiment counter."""
        key = "icyquant_experiments_total"
        self._counters[key] = self._counters.get(key, 0) + 1

    def set_active_sessions(self, count: int) -> None:
        """Set active workspace sessions gauge."""
        self._gauges["icyquant_research_workspace_sessions"] = float(count)

    def set_knowledge_documents(self, count: int) -> None:
        """Set knowledge document count gauge."""
        self._gauges["icyquant_knowledge_documents_total"] = float(count)

    def increment_citation(self) -> None:
        """Increment citation counter."""
        key = "icyquant_citation_total"
        self._counters[key] = self._counters.get(key, 0) + 1

    def record_api_latency(self, latency_ms: float, endpoint: str = "") -> None:
        """Record API call latency."""
        key = "icyquant_research_api_latency"
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(latency_ms)

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines: list[str] = []

        # Counters
        for name, value in self._counters.items():
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{name} {value}")

        # Gauges
        for name, value in self._gauges.items():
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{name} {value}")

        # Histograms
        for name, values in self._histograms.items():
            if values:
                lines.append(f"# TYPE {name} histogram")
                lines.append(f"{name}_sum {sum(values)}")
                lines.append(f"{name}_count {len(values)}")
                avg = sum(values) / len(values) if values else 0
                lines.append(f"{name}_avg {avg:.2f}")

        return "\n".join(lines)

    def get_snapshot(self) -> dict[str, Any]:
        """Get a snapshot of all metrics."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                name: {
                    "count": len(values),
                    "sum": sum(values),
                    "avg": sum(values) / len(values) if values else 0,
                }
                for name, values in self._histograms.items()
            },
            "uptime_seconds": time.time() - self._start_time,
        }

    @property
    def total_requests(self) -> int:
        return int(self._counters.get("icyquant_research_requests_total", 0))

    @property
    def total_reports(self) -> int:
        return int(self._counters.get("icyquant_reports_generated_total", 0))

    @property
    def total_experiments(self) -> int:
        return int(self._counters.get("icyquant_experiments_total", 0))
