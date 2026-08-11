"""Agent Metrics — Prometheus-compatible metrics for the multi-agent collaboration subsystem.

Metrics exposed:
    icyquant_agents_total           — Gauge: total registered agents
    icyquant_agent_messages_total   — Counter: messages sent/received
    icyquant_agent_consensus_total  — Counter: consensus decisions made
    icyquant_agent_conflicts_total  — Counter: conflicts detected
    icyquant_agent_task_duration    — Histogram: task execution duration (ms)
    icyquant_agent_queue_depth      — Gauge: current task queue depth
    icyquant_agent_recovery_total   — Counter: agent recoveries triggered
"""

from __future__ import annotations

import logging
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Dict, Iterator, List, Optional, Tuple

logger = logging.getLogger(__name__)

# Use simple in-memory counters/gauges; replace with prometheus_client
# when the infrastructure layer provides a PrometheusRegistry adapter.
# All public methods are designed to map directly to prometheus_client
# counter.inc() / gauge.set() / histogram.observe().


@dataclass
class _MetricSnapshot:
    """Snapshot of a counter or gauge."""

    name: str
    type: str  # "counter" | "gauge" | "histogram"
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.monotonic)


class AgentMetrics:
    """Collector for multi-agent collaboration metrics.

    Thread-safe in-process metrics store that mirrors the Prometheus
    data model.  When the infrastructure PrometheusRegistry is available,
    these metrics can be registered as an additional collector.

    Usage:
        metrics = AgentMetrics()
        metrics.agents_total.set(5)
        metrics.agent_messages_total.inc()
        metrics.agent_task_duration.observe(123.4, labels={"agent": "market_agent"})
        print(metrics.to_dict())
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._label_ref: Dict[str, Dict[Tuple[Tuple[str, str], ...], str]] = {}
        logger.info("AgentMetrics initialized")

    # ── Metric Constructors ──

    def counter(self, name: str, description: str = "") -> "_CounterHandle":
        """Create or return a counter handle.

        Args:
            name: Prometheus metric name, e.g. "icyquant_agent_messages_total".
            description: Help text (not displayed in-process, passed through
                when registering with Prometheus).

        Returns:
            A handle that supports `inc(n)`, `get()`.
        """
        return _CounterHandle(name, self)

    def gauge(self, name: str, description: str = "") -> "_GaugeHandle":
        """Create or return a gauge handle.

        Args:
            name: Prometheus metric name, e.g. "icyquant_agents_total".
            description: Help text.

        Returns:
            A handle that supports `set(v)`, `inc(n)`, `dec(n)`, `get()`.
        """
        return _GaugeHandle(name, self)

    def histogram(self, name: str, description: str = "", buckets: Optional[List[float]] = None) -> "_HistogramHandle":
        """Create or return a histogram handle.

        Args:
            name: Metric name, e.g. "icyquant_agent_task_duration".
            description: Help text.
            buckets: Custom bucket boundaries (default: [1, 5, 10, 25, 50, 100, 250, 500, 1000]).

        Returns:
            A handle that supports `observe(v)`.
        """
        return _HistogramHandle(name, self, buckets)

    # ── Internal Mutators ──

    def _inc_counter(self, name: str, amount: float = 1.0) -> None:
        with self._lock:
            self._counters[name] = self._counters.get(name, 0.0) + amount

    def _set_gauge(self, name: str, value: float) -> None:
        with self._lock:
            self._gauges[name] = value

    def _add_histogram(self, name: str, value: float) -> None:
        with self._lock:
            self._histograms.setdefault(name, []).append(value)

    # ── Helpers ──

    @staticmethod
    def _make_label_key(labels: Optional[Dict[str, str]] = None) -> str:
        """Serialize label dict to a stable string key."""
        if not labels:
            return ""
        return "|".join(f"{k}={v}" for k, v in sorted(labels.items()))

    # ── Snapshot / Export ──

    def to_dict(self) -> Dict[str, Any]:
        """Export all metrics as a JSON-safe dict.

        Returns:
            Dict with counters, gauges, and histogram summaries.
        """
        with self._lock:
            counters = dict(self._counters)
            gauges = dict(self._gauges)
            histograms = {}
            for name, values in self._histograms.items():
                if not values:
                    histograms[name] = {"count": 0, "sum": 0.0, "min": 0, "max": 0, "avg": 0}
                else:
                    histograms[name] = {
                        "count": len(values),
                        "sum": sum(values),
                        "min": min(values),
                        "max": max(values),
                        "avg": sum(values) / len(values),
                    }
            return {
                "counters": counters,
                "gauges": gauges,
                "histograms": histograms,
            }

    def snapshot(self) -> List[_MetricSnapshot]:
        """Return a flat list of metric snapshots.

        Returns:
            List of _MetricSnapshot objects.
        """
        snapshots: List[_MetricSnapshot] = []
        with self._lock:
            for name, value in self._counters.items():
                snapshots.append(_MetricSnapshot(name=name, type="counter", value=value))
            for name, value in self._gauges.items():
                snapshots.append(_MetricSnapshot(name=name, type="gauge", value=value))
            for name, values in self._histograms.items():
                for v in values:
                    snapshots.append(_MetricSnapshot(name=name, type="histogram", value=v))
        return snapshots

    # ── Built-in Metrics (convenience) ──

    @property
    def agents_total(self) -> "_GaugeHandle":
        """icyquant_agents_total — number of registered agents."""
        return self.gauge("icyquant_agents_total", "Total registered agents")

    @property
    def agent_messages_total(self) -> "_CounterHandle":
        """icyquant_agent_messages_total — messages sent/received."""
        return self.counter("icyquant_agent_messages_total", "Total messages exchanged")

    @property
    def agent_consensus_total(self) -> "_CounterHandle":
        """icyquant_agent_consensus_total — consensus decisions made."""
        return self.counter("icyquant_agent_consensus_total", "Total consensus decisions")

    @property
    def agent_conflicts_total(self) -> "_CounterHandle":
        """icyquant_agent_conflicts_total — conflicts detected."""
        return self.counter("icyquant_agent_conflicts_total", "Total conflicts detected")

    @property
    def agent_task_duration(self) -> "_HistogramHandle":
        """icyquant_agent_task_duration — task execution duration (ms)."""
        return self.histogram("icyquant_agent_task_duration", "Task execution duration in ms")

    @property
    def agent_queue_depth(self) -> "_GaugeHandle":
        """icyquant_agent_queue_depth — current task queue depth."""
        return self.gauge("icyquant_agent_queue_depth", "Current task queue depth")

    @property
    def agent_recovery_total(self) -> "_CounterHandle":
        """icyquant_agent_recovery_total — agent recoveries triggered."""
        return self.counter("icyquant_agent_recovery_total", "Total agent recoveries")


# ── Handle Classes ──


class _CounterHandle:
    """Handle for incrementing a counter."""

    def __init__(self, name: str, parent: AgentMetrics) -> None:
        self._name = name
        self._parent = parent

    def inc(self, amount: float = 1.0) -> None:
        """Increment the counter.

        Args:
            amount: Amount to increment (default 1).
        """
        self._parent._inc_counter(self._name, amount)

    def get(self) -> float:
        """Get current counter value."""
        with self._parent._lock:
            return self._parent._counters.get(self._name, 0.0)


class _GaugeHandle:
    """Handle for setting/reading a gauge."""

    def __init__(self, name: str, parent: AgentMetrics) -> None:
        self._name = name
        self._parent = parent

    def set(self, value: float) -> None:
        """Set gauge to an absolute value.

        Args:
            value: The absolute value.
        """
        self._parent._set_gauge(self._name, value)

    def inc(self, amount: float = 1.0) -> None:
        """Increment gauge by amount.

        Args:
            amount: Amount to add.
        """
        with self._parent._lock:
            current = self._parent._gauges.get(self._name, 0.0)
            self._parent._gauges[self._name] = current + amount

    def dec(self, amount: float = 1.0) -> None:
        """Decrement gauge by amount.

        Args:
            amount: Amount to subtract.
        """
        self.inc(-amount)

    def get(self) -> float:
        """Get current gauge value."""
        with self._parent._lock:
            return self._parent._gauges.get(self._name, 0.0)


class _HistogramHandle:
    """Handle for observing values into a histogram."""

    def __init__(
        self,
        name: str,
        parent: AgentMetrics,
        buckets: Optional[List[float]] = None,
    ) -> None:
        self._name = name
        self._parent = parent
        self._buckets = buckets or [1, 5, 10, 25, 50, 100, 250, 500, 1000]

    def observe(self, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a histogram observation.

        Args:
            value: The observed value.
            labels: Optional dict of metric labels.
        """
        self._parent._add_histogram(self._name, value)
