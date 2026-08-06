"""Integration Metrics — Prometheus-compatible metrics for the research platform.

Commit 11 Part 1.5: Exposes platform-level metrics for monitoring
research activity, model lifecycle, and integration health.

Metrics:
    icyquant_research_platform_total      — Platform operations counter
    icyquant_research_models_total        — Registered models gauge
    icyquant_research_experiments_total   — Experiment operations counter
    icyquant_research_backtests_total     — Backtest operations counter
    icyquant_research_portfolios_total    — Portfolio operations counter
    icyquant_research_ai_runtime_total    — AI runtime operations counter
    icyquant_research_publish_total       — Publish operations counter
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from uuid import uuid4

logger = logging.getLogger(__name__)


@dataclass
class MetricValue:
    """A single metric observation."""

    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class IntegrationMetrics:
    """Prometheus-compatible metrics collector for the research platform.

    Tracks platform-level counters, gauges, and histograms for
    monitoring research operations.

    Usage::

        metrics = IntegrationMetrics()
        metrics.increment_platform_operations("experiment_created")
        metrics.set_models_total(42)
    """

    def __init__(self, *, metrics_id: Optional[str] = None) -> None:
        self._id: str = metrics_id or f"im-{uuid4().hex[:12]}"

        # Counters
        self._platform_total: int = 0
        self._experiments_total: int = 0
        self._backtests_total: int = 0
        self._portfolios_total: int = 0
        self._ai_runtime_total: int = 0
        self._publish_total: int = 0

        # Gauges
        self._models_total: int = 0

        # Histograms (simplified as lists for demo)
        self._platform_latency: List[float] = []
        self._observations: List[MetricValue] = []

    # ------------------------------------------------------------------
    # Properties
    # ------------------------------------------------------------------

    @property
    def id(self) -> str:
        return self._id

    # ------------------------------------------------------------------
    # Counter Operations
    # ------------------------------------------------------------------

    def increment_platform_operations(self, operation: str) -> None:
        """Increment platform operations counter.

        Args:
            operation: Operation label (e.g., experiment_created, workflow_started).
        """
        self._platform_total += 1
        self._record(MetricValue("icyquant_research_platform_total", float(self._platform_total),
                                 {"operation": operation}))

    def increment_experiments(self, status: str) -> None:
        """Increment experiments counter."""
        self._experiments_total += 1
        self._record(MetricValue("icyquant_research_experiments_total", float(self._experiments_total),
                                 {"status": status}))

    def increment_backtests(self, status: str) -> None:
        """Increment backtests counter."""
        self._backtests_total += 1
        self._record(MetricValue("icyquant_research_backtests_total", float(self._backtests_total),
                                 {"status": status}))

    def increment_portfolios(self, status: str) -> None:
        """Increment portfolios counter."""
        self._portfolios_total += 1
        self._record(MetricValue("icyquant_research_portfolios_total", float(self._portfolios_total),
                                 {"status": status}))

    def increment_ai_runtime(self, task_type: str) -> None:
        """Increment AI runtime operations counter."""
        self._ai_runtime_total += 1
        self._record(MetricValue("icyquant_research_ai_runtime_total", float(self._ai_runtime_total),
                                 {"task_type": task_type}))

    def increment_publish(self, result_type: str) -> None:
        """Increment publish operations counter."""
        self._publish_total += 1
        self._record(MetricValue("icyquant_research_publish_total", float(self._publish_total),
                                 {"result_type": result_type}))

    # ------------------------------------------------------------------
    # Gauge Operations
    # ------------------------------------------------------------------

    def set_models_total(self, count: int) -> None:
        """Set registered models gauge."""
        self._models_total = count
        self._record(MetricValue("icyquant_research_models_total", float(count)))

    # ------------------------------------------------------------------
    # Histogram Operations
    # ------------------------------------------------------------------

    def observe_platform_latency(self, duration_ms: float, operation: str) -> None:
        """Record platform operation latency.

        Args:
            duration_ms: Operation duration in milliseconds.
            operation: Operation label.
        """
        self._platform_latency.append(duration_ms)
        self._record(MetricValue("icyquant_research_platform_latency_ms", duration_ms,
                                 {"operation": operation}))

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _record(self, observation: MetricValue) -> None:
        """Record a metric observation."""
        self._observations.append(observation)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def to_prometheus_format(self) -> str:
        """Export all metrics in Prometheus text format.

        Returns:
            Prometheus-formatted metric string.
        """
        lines = [
            "# HELP icyquant_research_platform_total Total platform operations",
            "# TYPE icyquant_research_platform_total counter",
            f"icyquant_research_platform_total {self._platform_total}",
            "",
            "# HELP icyquant_research_models_total Total registered models",
            "# TYPE icyquant_research_models_total gauge",
            f"icyquant_research_models_total {self._models_total}",
            "",
            "# HELP icyquant_research_experiments_total Total experiment operations",
            "# TYPE icyquant_research_experiments_total counter",
            f"icyquant_research_experiments_total {self._experiments_total}",
            "",
            "# HELP icyquant_research_backtests_total Total backtest operations",
            "# TYPE icyquant_research_backtests_total counter",
            f"icyquant_research_backtests_total {self._backtests_total}",
            "",
            "# HELP icyquant_research_portfolios_total Total portfolio operations",
            "# TYPE icyquant_research_portfolios_total counter",
            f"icyquant_research_portfolios_total {self._portfolios_total}",
            "",
            "# HELP icyquant_research_ai_runtime_total Total AI runtime operations",
            "# TYPE icyquant_research_ai_runtime_total counter",
            f"icyquant_research_ai_runtime_total {self._ai_runtime_total}",
            "",
            "# HELP icyquant_research_publish_total Total publish operations",
            "# TYPE icyquant_research_publish_total counter",
            f"icyquant_research_publish_total {self._publish_total}",
        ]
        return "\n".join(lines)

    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        return {
            "metrics_id": self._id,
            "counters": {
                "platform_total": self._platform_total,
                "experiments_total": self._experiments_total,
                "backtests_total": self._backtests_total,
                "portfolios_total": self._portfolios_total,
                "ai_runtime_total": self._ai_runtime_total,
                "publish_total": self._publish_total,
            },
            "gauges": {
                "models_total": self._models_total,
            },
            "observation_count": len(self._observations),
        }

    def reset(self) -> None:
        """Reset all metrics to zero."""
        self._platform_total = 0
        self._experiments_total = 0
        self._backtests_total = 0
        self._portfolios_total = 0
        self._ai_runtime_total = 0
        self._publish_total = 0
        self._models_total = 0
        self._platform_latency.clear()
        self._observations.clear()
