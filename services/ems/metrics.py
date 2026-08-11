"""EMS Metrics — Prometheus metrics for the Execution Management System.

Defines and manages all EMS-specific Prometheus metrics for monitoring
execution performance, algorithm behavior, and system health.

Metrics:
    icyquant_execution_tasks_total: Counter of total execution tasks
    icyquant_child_orders_total: Counter of child orders created
    icyquant_execution_latency: Histogram of execution latency
    icyquant_execution_fill_rate: Gauge of current fill rate
    icyquant_execution_slippage: Histogram of execution slippage
    icyquant_execution_quality_score: Gauge of execution quality scores
    icyquant_algorithm_switch_total: Counter of algorithm switches
    icyquant_execution_active_tasks: Gauge of active execution tasks

Usage::

    metrics = EMSMetrics()
    metrics.record_execution_task("TWAP")
    metrics.record_child_order_created("VWAP")
    metrics.record_transition_latency("PENDING", "ACTIVE", 0.5)
"""

from __future__ import annotations

import logging
import time
from typing import Any, Optional

logger = logging.getLogger(__name__)


class EMSMetrics:
    """EMS Prometheus metrics registry.

    Provides structured metrics for execution monitoring.
    In production, these would be backed by the prometheus_client library.
    This implementation provides a compatible interface for development.

    Attributes:
        _counters: Counter metrics
        _histograms: Histogram metrics
        _gauges: Gauge metrics
    """

    def __init__(self) -> None:
        self._counters: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}
        self._gauges: dict[str, float] = {}

        # Initialize counters
        self._counters["icyquant_execution_tasks_total"] = 0.0
        self._counters["icyquant_child_orders_total"] = 0.0
        self._counters["icyquant_algorithm_switch_total"] = 0.0
        self._counters["icyquant_execution_completed_total"] = 0.0
        self._counters["icyquant_execution_cancelled_total"] = 0.0
        self._counters["icyquant_execution_rejected_total"] = 0.0
        self._counters["icyquant_execution_error_total"] = 0.0
        self._counters["icyquant_execution_paused_total"] = 0.0

        # Initialize histograms
        self._histograms["icyquant_execution_latency"] = []
        self._histograms["icyquant_execution_slippage"] = []
        self._histograms["icyquant_transition_latency"] = []

        # Initialize gauges
        self._gauges["icyquant_execution_fill_rate"] = 0.0
        self._gauges["icyquant_execution_quality_score"] = 0.0
        self._gauges["icyquant_execution_active_tasks"] = 0.0

    # ── Counters ───────────────────────────────────────────────────

    def record_execution_task(self, strategy: str) -> None:
        """Record a new execution task.

        Args:
            strategy: Algorithm strategy name
        """
        self._counters["icyquant_execution_tasks_total"] += 1
        logger.debug("Execution task recorded: strategy=%s total=%.0f", strategy, self._counters["icyquant_execution_tasks_total"])

    def record_child_order_created(self, strategy: str) -> None:
        """Record a child order creation.

        Args:
            strategy: Algorithm strategy name
        """
        self._counters["icyquant_child_orders_total"] += 1

    def record_child_order_filled(self) -> None:
        """Record a child order fill completion."""
        pass  # Tracked via child_orders_total

    def record_algorithm_switch(self, from_strategy: str, to_strategy: str) -> None:
        """Record an algorithm strategy switch.

        Args:
            from_strategy: Previous strategy
            to_strategy: New strategy
        """
        self._counters["icyquant_algorithm_switch_total"] += 1
        logger.info("Algorithm switch: %s → %s", from_strategy, to_strategy)

    def record_execution_completed(self) -> None:
        """Record a completed execution."""
        self._counters["icyquant_execution_completed_total"] += 1

    def record_execution_cancelled(self) -> None:
        """Record a cancelled execution."""
        self._counters["icyquant_execution_cancelled_total"] += 1

    def record_execution_rejected(self) -> None:
        """Record a rejected execution."""
        self._counters["icyquant_execution_rejected_total"] += 1

    def record_execution_error(self) -> None:
        """Record an execution error."""
        self._counters["icyquant_execution_error_total"] += 1

    def record_execution_paused(self) -> None:
        """Record a paused execution."""
        self._counters["icyquant_execution_paused_total"] += 1

    # ── Histograms ─────────────────────────────────────────────────

    def record_execution_latency(self, duration_seconds: float) -> None:
        """Record execution latency.

        Args:
            duration_seconds: Execution duration in seconds
        """
        self._histograms["icyquant_execution_latency"].append(duration_seconds)

    def record_slippage(self, slippage_bps: float) -> None:
        """Record execution slippage.

        Args:
            slippage_bps: Slippage in basis points
        """
        self._histograms["icyquant_execution_slippage"].append(slippage_bps)

    def record_transition_latency(self, from_status: str, to_status: str, duration_seconds: float = 0.0) -> None:
        """Record state transition latency.

        Args:
            from_status: Source status
            to_status: Target status
            duration_seconds: Transition duration
        """
        self._histograms["icyquant_transition_latency"].append(duration_seconds)

    # ── Gauges ─────────────────────────────────────────────────────

    def record_fill_rate(self, fill_pct: float) -> None:
        """Record current fill rate.

        Args:
            fill_pct: Fill percentage (0-1)
        """
        self._gauges["icyquant_execution_fill_rate"] = fill_pct

    def record_quality_score(self, score: float) -> None:
        """Record execution quality score.

        Args:
            score: Quality score (0-100)
        """
        self._gauges["icyquant_execution_quality_score"] = score

    def record_active_tasks(self, count: int) -> None:
        """Record active task count.

        Args:
            count: Number of active execution tasks
        """
        self._gauges["icyquant_execution_active_tasks"] = float(count)

    # ── Query API ──────────────────────────────────────────────────

    def get_counter(self, name: str) -> float:
        """Get a counter value.

        Args:
            name: Counter metric name

        Returns:
            Counter value
        """
        return self._counters.get(name, 0.0)

    def get_gauge(self, name: str) -> float:
        """Get a gauge value.

        Args:
            name: Gauge metric name

        Returns:
            Gauge value
        """
        return self._gauges.get(name, 0.0)

    def get_histogram_stats(self, name: str) -> dict[str, float]:
        """Get histogram statistics.

        Args:
            name: Histogram metric name

        Returns:
            Dict with count, sum, avg, min, max
        """
        values = self._histograms.get(name, [])
        if not values:
            return {"count": 0, "sum": 0.0, "avg": 0.0, "min": 0.0, "max": 0.0}

        return {
            "count": len(values),
            "sum": sum(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
        }

    def to_dict(self) -> dict[str, Any]:
        """Serialize all metrics to dictionary."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                name: self.get_histogram_stats(name)
                for name in self._histograms
            },
        }
