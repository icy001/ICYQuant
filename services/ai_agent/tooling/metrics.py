"""Tool Metrics — Prometheus-compatible metrics for the tool calling subsystem.

Metrics:
    icyquant_tool_calls_total
    icyquant_tool_success_total
    icyquant_tool_failure_total
    icyquant_tool_retry_total
    icyquant_tool_cache_hit_ratio
    icyquant_tool_execution_latency
    icyquant_tool_permission_denied_total
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ── Metric Types ──

@dataclass
class Counter:
    """A monotonically increasing counter metric."""

    name: str
    help: str = ""
    value: int = 0
    labels: Dict[str, str] = field(default_factory=dict)

    def inc(self, amount: int = 1) -> None:
        """Increment the counter."""
        self.value += amount

    def export(self) -> Dict[str, Any]:
        """Export in Prometheus text format."""
        label_str = ",".join(f'{k}="{v}"' for k, v in self.labels.items())
        label_part = f"{{{label_str}}}" if label_str else ""
        return {
            "name": self.name,
            "value": self.value,
            "help": self.help,
            "labels": self.labels,
        }


@dataclass
class Gauge:
    """A gauge metric that can go up and down."""

    name: str
    help: str = ""
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)

    def set(self, value: float) -> None:
        """Set the gauge value."""
        self.value = value

    def inc(self, amount: float = 1.0) -> None:
        """Increment the gauge."""
        self.value += amount

    def dec(self, amount: float = 1.0) -> None:
        """Decrement the gauge."""
        self.value -= amount

    def export(self) -> Dict[str, Any]:
        """Export in Prometheus text format."""
        return {
            "name": self.name,
            "value": self.value,
            "help": self.help,
            "labels": self.labels,
        }


@dataclass
class Histogram:
    """A histogram metric for distribution tracking."""

    name: str
    help: str = ""
    buckets: List[float] = field(default_factory=lambda: [0.01, 0.05, 0.1, 0.5, 1, 5, 10, 30, 60, 300])
    values: List[float] = field(default_factory=list)
    sum_value: float = 0.0
    count: int = 0
    labels: Dict[str, str] = field(default_factory=dict)

    def observe(self, value: float) -> None:
        """Record an observation."""
        self.values.append(value)
        self.sum_value += value
        self.count += 1
        # Keep last 1000 observations
        if len(self.values) > 1000:
            self.values = self.values[-1000:]

    def export(self) -> Dict[str, Any]:
        """Export the histogram data."""
        if not self.values:
            return {
                "name": self.name,
                "count": 0,
                "sum": 0,
                "avg": 0,
                "p50": 0,
                "p95": 0,
                "p99": 0,
                "help": self.help,
            }
        sorted_values = sorted(self.values)
        n = len(sorted_values)
        return {
            "name": self.name,
            "count": self.count,
            "sum": round(self.sum_value, 3),
            "avg": round(self.sum_value / self.count, 3) if self.count else 0,
            "p50": round(sorted_values[int(n * 0.50)], 3),
            "p95": round(sorted_values[int(n * 0.95)], 3),
            "p99": round(sorted_values[int(n * 0.99)], 3),
            "help": self.help,
        }


# ── ToolMetrics ──

class ToolMetrics:
    """Metrics collector for the tool calling subsystem.

    Provides Prometheus-compatible counters, gauges, and histograms
    for tracking tool call volume, success/failure rates, latency,
    cache performance, and permission outcomes.

    Supports:
        - Total calls, success, failure counters
        - Retry counter
        - Cache hit ratio gauge
        - Execution latency histogram
        - Permission denied counter
        - Per-tool label support

    Usage:
        metrics = ToolMetrics()
        metrics.tool_calls_total.inc()
        metrics.tool_execution_latency.observe(125.3)
        summary = metrics.get_summary()
    """

    def __init__(self) -> None:
        """Initialize all metrics."""
        # ── Counters ──
        self.tool_calls_total = Counter(
            name="icyquant_tool_calls_total",
            help="Total number of tool calls",
        )
        self.tool_success_total = Counter(
            name="icyquant_tool_success_total",
            help="Total number of successful tool calls",
        )
        self.tool_failure_total = Counter(
            name="icyquant_tool_failure_total",
            help="Total number of failed tool calls",
        )
        self.tool_retry_total = Counter(
            name="icyquant_tool_retry_total",
            help="Total number of tool retry attempts",
        )
        self.tool_permission_denied_total = Counter(
            name="icyquant_tool_permission_denied_total",
            help="Total number of permission denied tool calls",
        )

        # ── Gauges ──
        self.tool_cache_hit_ratio = Gauge(
            name="icyquant_tool_cache_hit_ratio",
            help="Cache hit ratio for tool calls",
        )
        self.tool_active_executions = Gauge(
            name="icyquant_tool_active_executions",
            help="Number of currently active tool executions",
        )

        # ── Histograms ──
        self.tool_execution_latency = Histogram(
            name="icyquant_tool_execution_latency_seconds",
            help="Tool execution latency in seconds",
        )

        # ── Per-tool counters ──
        self._per_tool_calls: Dict[str, int] = {}
        self._per_tool_success: Dict[str, int] = {}
        self._per_tool_failure: Dict[str, int] = {}
        self._per_tool_cache_hits: Dict[str, int] = {}
        self._per_tool_cache_misses: Dict[str, int] = {}

        self._initialized: bool = False
        logger.info("ToolMetrics created")

    # ── Lifecycle ──

    async def initialize(self) -> None:
        """Initialize metrics."""
        self._initialized = True
        logger.info("ToolMetrics initialized")

    async def shutdown(self) -> None:
        """Shutdown metrics."""
        self._initialized = False
        logger.info("ToolMetrics shutdown complete")

    # ── Recording ──

    def record_call(
        self,
        tool_name: str,
        success: bool,
        latency_ms: float,
        from_cache: bool = False,
        was_retried: bool = False,
        permission_denied: bool = False,
        retry_count: int = 0,
    ) -> None:
        """Record a tool call with all metrics.

        Args:
            tool_name: The tool name.
            success: Whether the call succeeded.
            latency_ms: Execution latency in milliseconds.
            from_cache: Whether result was from cache.
            was_retried: Whether the call was retried.
            permission_denied: Whether permission was denied.
            retry_count: Number of retry attempts.
        """
        self.tool_calls_total.inc()
        self.tool_execution_latency.observe(latency_ms / 1000.0)

        if success:
            self.tool_success_total.inc()
        else:
            self.tool_failure_total.inc()

        if retry_count > 0:
            self.tool_retry_total.inc(retry_count)

        if permission_denied:
            self.tool_permission_denied_total.inc()

        # Per-tool tracking
        self._per_tool_calls[tool_name] = self._per_tool_calls.get(tool_name, 0) + 1
        if success:
            self._per_tool_success[tool_name] = self._per_tool_success.get(tool_name, 0) + 1
        else:
            self._per_tool_failure[tool_name] = self._per_tool_failure.get(tool_name, 0) + 1

        if from_cache:
            self._per_tool_cache_hits[tool_name] = self._per_tool_cache_hits.get(tool_name, 0) + 1
        else:
            self._per_tool_cache_misses[tool_name] = self._per_tool_cache_misses.get(tool_name, 0) + 1

    def set_active_executions(self, count: int) -> None:
        """Set the active executions gauge.

        Args:
            count: Current number of active executions.
        """
        self.tool_active_executions.set(float(count))

    # ── Per-tool Metrics ──

    def get_tool_cache_hit_ratio(self, tool_name: str) -> float:
        """Get cache hit ratio for a specific tool.

        Args:
            tool_name: The tool name.

        Returns:
            Cache hit ratio (0.0 to 1.0).
        """
        hits = self._per_tool_cache_hits.get(tool_name, 0)
        misses = self._per_tool_cache_misses.get(tool_name, 0)
        total = hits + misses
        if total == 0:
            return 0.0
        return hits / total

    def get_tool_success_rate(self, tool_name: str) -> float:
        """Get success rate for a specific tool.

        Args:
            tool_name: The tool name.

        Returns:
            Success rate (0.0 to 1.0).
        """
        total = self._per_tool_calls.get(tool_name, 0)
        if total == 0:
            return 1.0
        return self._per_tool_success.get(tool_name, 0) / total

    # ── Export ──

    def get_all_metrics(self) -> List[Dict[str, Any]]:
        """Export all metrics in Prometheus-compatible format."""
        return [
            self.tool_calls_total.export(),
            self.tool_success_total.export(),
            self.tool_failure_total.export(),
            self.tool_retry_total.export(),
            self.tool_permission_denied_total.export(),
            self.tool_cache_hit_ratio.export(),
            self.tool_active_executions.export(),
            self.tool_execution_latency.export(),
        ]

    def get_summary(self) -> Dict[str, Any]:
        """Get a human-readable metrics summary."""
        all_tools = set(list(self._per_tool_calls.keys()))

        return {
            "totals": {
                "calls": self.tool_calls_total.value,
                "success": self.tool_success_total.value,
                "failure": self.tool_failure_total.value,
                "retries": self.tool_retry_total.value,
                "permission_denied": self.tool_permission_denied_total.value,
                "active_executions": int(self.tool_active_executions.value),
            },
            "latency": self.tool_execution_latency.export(),
            "per_tool": {
                tool: {
                    "calls": self._per_tool_calls.get(tool, 0),
                    "success_rate": round(self.get_tool_success_rate(tool), 4),
                    "cache_hit_ratio": round(self.get_tool_cache_hit_ratio(tool), 4),
                }
                for tool in sorted(all_tools)
            },
            "initialized": self._initialized,
        }
