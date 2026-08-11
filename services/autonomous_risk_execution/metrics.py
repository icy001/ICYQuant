"""
Autonomous Risk & Execution Metrics — Prometheus-compatible metrics for monitoring the platform.

Provides counters, gauges, histograms, and summaries for tracking agent behavior,
risk optimization, execution flow, pre-trade validation, and kill-switch events.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class Metrics:
    """
    Prometheus-style metrics for the Autonomous Risk & Execution Optimization Platform.

    Tracks agent activity, risk decisions, execution lifecycle, pre-trade checks,
    and platform health via counters, gauges, histograms, and summaries.

    Metric Types:
        Counters: Monotonically increasing values (requests, events, totals).
        Gauges: Settable values that can go up or down (active portfolios, health).
        Histograms: Recordable distributions (duration measurements).
        Summaries: Aggregated statistics with quantile computation.

    Usage:
        metrics = Metrics()
        metrics.increment_counter("icyquant_agent_requests_total")
        metrics.set_gauge("icyquant_active_portfolios", 42.0)
        metrics.record_histogram("icyquant_risk_optimization_duration_seconds", 0.150)
        snapshot = metrics.get_metrics_snapshot()
    """

    # ── Counter Metric Names ──────────────────────────────────

    AGENT_REQUESTS_TOTAL = "icyquant_agent_requests_total"
    AGENT_SESSIONS_TOTAL = "icyquant_agent_sessions_total"
    AGENT_PLANS_TOTAL = "icyquant_agent_plans_total"
    AGENT_REASONING_TOTAL = "icyquant_agent_reasoning_total"
    AGENT_MEMORY_HITS = "icyquant_agent_memory_hits"
    AGENT_RUNTIME_SECONDS = "icyquant_agent_runtime_seconds"
    RISK_OPTIMIZATIONS_TOTAL = "icyquant_risk_optimizations_total"
    RISK_REJECTIONS_TOTAL = "icyquant_risk_rejections_total"
    RISK_RESIZES_TOTAL = "icyquant_risk_resizes_total"
    EXECUTION_ORDERS_TOTAL = "icyquant_execution_orders_total"
    EXECUTION_SLICES_TOTAL = "icyquant_execution_slices_total"
    EXECUTION_FILLS_TOTAL = "icyquant_execution_fills_total"
    PRE_TRADE_BLOCKS_TOTAL = "icyquant_pre_trade_blocks_total"
    KILL_SWITCH_ENGAGEMENTS_TOTAL = "icyquant_kill_switch_engagements_total"

    # ── Gauge Metric Names ────────────────────────────────────

    ACTIVE_PORTFOLIOS = "icyquant_active_portfolios"
    ACTIVE_ORDERS = "icyquant_active_orders"
    RISK_BUDGET_USED = "icyquant_risk_budget_used"
    PLATFORM_HEALTH = "icyquant_platform_health"

    # ── Histogram Metric Names ────────────────────────────────

    RISK_OPTIMIZATION_DURATION = "icyquant_risk_optimization_duration_seconds"
    EXECUTION_PLANNING_DURATION = "icyquant_execution_planning_duration_seconds"
    PRE_TRADE_VALIDATION_DURATION = "icyquant_pre_trade_validation_duration_seconds"
    FEEDBACK_PROCESSING_DURATION = "icyquant_feedback_processing_duration_seconds"
    PIPELINE_DURATION = "icyquant_pipeline_duration_seconds"

    # ── Summary Metric Names ──────────────────────────────────

    AGENT_DECISION_SUMMARY = "icyquant_agent_decision_summary"
    EXECUTION_COST_SUMMARY = "icyquant_execution_cost_summary"

    # ── Counter Namespace ─────────────────────────────────────

    _COUNTER_NAMES: tuple[str, ...] = (
        AGENT_REQUESTS_TOTAL,
        AGENT_SESSIONS_TOTAL,
        AGENT_PLANS_TOTAL,
        AGENT_REASONING_TOTAL,
        AGENT_MEMORY_HITS,
        AGENT_RUNTIME_SECONDS,
        RISK_OPTIMIZATIONS_TOTAL,
        RISK_REJECTIONS_TOTAL,
        RISK_RESIZES_TOTAL,
        EXECUTION_ORDERS_TOTAL,
        EXECUTION_SLICES_TOTAL,
        EXECUTION_FILLS_TOTAL,
        PRE_TRADE_BLOCKS_TOTAL,
        KILL_SWITCH_ENGAGEMENTS_TOTAL,
    )

    _GAUGE_NAMES: tuple[str, ...] = (
        ACTIVE_PORTFOLIOS,
        ACTIVE_ORDERS,
        RISK_BUDGET_USED,
        PLATFORM_HEALTH,
    )

    _HISTOGRAM_NAMES: tuple[str, ...] = (
        RISK_OPTIMIZATION_DURATION,
        EXECUTION_PLANNING_DURATION,
        PRE_TRADE_VALIDATION_DURATION,
        FEEDBACK_PROCESSING_DURATION,
        PIPELINE_DURATION,
    )

    _SUMMARY_NAMES: tuple[str, ...] = (
        AGENT_DECISION_SUMMARY,
        EXECUTION_COST_SUMMARY,
    )

    def __init__(self) -> None:
        """
        Initialize the Metrics registry.

        Sets up internal storage for counters, gauges, histograms, and summaries
        with default values. All counters start at zero; gauges, histograms, and
        summaries start empty.
        """
        self._counters: dict[str, float] = {
            name: 0.0 for name in self._COUNTER_NAMES
        }
        self._gauges: dict[str, float] = {
            name: 0.0 for name in self._GAUGE_NAMES
        }
        self._histograms: dict[str, list[float]] = {
            name: [] for name in self._HISTOGRAM_NAMES
        }
        self._summaries: dict[str, list[float]] = {
            name: [] for name in self._SUMMARY_NAMES
        }
        logger.info("Autonomous Risk & Execution Metrics initialized.")

    # ── Counter Operations ────────────────────────────────────

    async def increment_counter(
        self, name: str, amount: float = 1.0,
    ) -> None:
        """
        Increment a Prometheus counter by the given amount.

        Args:
            name: The counter metric name (must be a registered counter).
            amount: The value to increment by (default 1.0).

        Raises:
            ValueError: If the metric name is not a registered counter.
        """
        if name not in self._counters:
            raise ValueError(
                f"Unknown counter metric: {name}. "
                f"Valid counters: {self._COUNTER_NAMES}"
            )
        self._counters[name] += amount

    # ── Gauge Operations ──────────────────────────────────────

    async def set_gauge(self, name: str, value: float) -> None:
        """
        Set a Prometheus gauge to an absolute value.

        Args:
            name: The gauge metric name (must be a registered gauge).
            value: The value to set the gauge to.

        Raises:
            ValueError: If the metric name is not a registered gauge.
        """
        if name not in self._gauges:
            raise ValueError(
                f"Unknown gauge metric: {name}. "
                f"Valid gauges: {self._GAUGE_NAMES}"
            )
        self._gauges[name] = value

    # ── Histogram Operations ──────────────────────────────────

    async def record_histogram(
        self, name: str, value: float,
    ) -> None:
        """
        Record a single observation into a Prometheus histogram.

        Stores the value in the histogram's observation buffer. When the
        buffer exceeds 10,000 entries, it is truncated to the most recent
        10,000 observations to bound memory usage.

        Args:
            name: The histogram metric name (must be a registered histogram).
            value: The observation value (e.g., duration in seconds).

        Raises:
            ValueError: If the metric name is not a registered histogram.
        """
        if name not in self._histograms:
            raise ValueError(
                f"Unknown histogram metric: {name}. "
                f"Valid histograms: {self._HISTOGRAM_NAMES}"
            )
        self._histograms[name].append(value)
        if len(self._histograms[name]) > 10000:
            self._histograms[name] = self._histograms[name][-10000:]

    # ── Summary Operations ───────────────────────────────────

    async def record_summary(
        self, name: str, value: float,
    ) -> None:
        """
        Record a single observation into a Prometheus summary.

        Summaries track observations and compute quantile statistics on
        demand via the snapshot method. When the buffer exceeds 10,000
        entries, it is truncated to the most recent 10,000 observations.

        Args:
            name: The summary metric name (must be a registered summary).
            value: The observation value.

        Raises:
            ValueError: If the metric name is not a registered summary.
        """
        if name not in self._summaries:
            raise ValueError(
                f"Unknown summary metric: {name}. "
                f"Valid summaries: {self._SUMMARY_NAMES}"
            )
        self._summaries[name].append(value)
        if len(self._summaries[name]) > 10000:
            self._summaries[name] = self._summaries[name][-10000:]

    # ── Snapshot ──────────────────────────────────────────────

    async def get_metrics_snapshot(self) -> dict[str, Any]:
        """
        Produce a point-in-time snapshot of all metrics.

        Returns counters, gauges, histogram statistics (count, min, max,
        avg, p50, p95, p99), and summary statistics in a single
        dictionary suitable for Prometheus exposition format conversion.

        Returns:
            A dictionary with keys "counters", "gauges", "histograms",
            and "summaries", each mapping metric names to their current
            values or computed statistics.
        """
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histograms": {
                name: self._compute_histogram_stats(
                    self._histograms[name],
                )
                for name in self._histograms
            },
            "summaries": {
                name: self._compute_summary_stats(
                    self._summaries[name],
                )
                for name in self._summaries
            },
        }

    # ── Reset ────────────────────────────────────────────────

    async def reset(self) -> None:
        """
        Reset all counters to zero and clear all gauges, histograms,
        and summaries. Intended for testing or administrative use.
        """
        for key in self._counters:
            self._counters[key] = 0.0
        for key in self._gauges:
            self._gauges[key] = 0.0
        for key in self._histograms:
            self._histograms[key] = []
        for key in self._summaries:
            self._summaries[key] = []
        logger.info("Autonomous Risk & Execution metrics reset.")

    # ── Internal Helpers ──────────────────────────────────────

    @staticmethod
    def _compute_histogram_stats(
        values: list[float],
    ) -> Optional[dict[str, float]]:
        """
        Compute summary statistics for a histogram's observation buffer.

        Args:
            values: The list of recorded observations.

        Returns:
            A dictionary with count, min, max, avg, p50, p95, and p99
            keys, or None if the buffer is empty.
        """
        if not values:
            return None
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        return {
            "count": float(n),
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "avg": sum(sorted_vals) / n,
            "p50": sorted_vals[int(n * 0.5)],
            "p95": sorted_vals[int(n * 0.95)] if n >= 20 else sorted_vals[-1],
            "p99": sorted_vals[int(n * 0.99)] if n >= 100 else sorted_vals[-1],
        }

    @staticmethod
    def _compute_summary_stats(
        values: list[float],
    ) -> Optional[dict[str, float]]:
        """
        Compute quantile statistics for a summary's observation buffer.

        Args:
            values: The list of recorded observations.

        Returns:
            A dictionary with count, sum, avg, q50, q90, q95, and q99
            keys, or None if the buffer is empty.
        """
        if not values:
            return None
        sorted_vals = sorted(values)
        n = len(sorted_vals)
        total = sum(sorted_vals)
        return {
            "count": float(n),
            "sum": total,
            "avg": total / n,
            "q50": sorted_vals[int(n * 0.5)],
            "q90": sorted_vals[int(n * 0.9)] if n >= 10 else sorted_vals[-1],
            "q95": sorted_vals[int(n * 0.95)] if n >= 20 else sorted_vals[-1],
            "q99": sorted_vals[int(n * 0.99)] if n >= 100 else sorted_vals[-1],
        }