"""
Strategy Platform Metrics — Prometheus-compatible instrumentation.

Exposes counters and gauges for strategy operations:
    icyquant_strategy_total          — Total strategies registered
    icyquant_strategy_running         — Currently running strategies
    icyquant_strategy_deploy_total    — Total deployments
    icyquant_strategy_restart_total   — Total restarts
    icyquant_strategy_snapshot_total  — Total snapshots
    icyquant_strategy_recovery_total  — Total recovery attempts
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


@dataclass
class Metric:
    """A single metric value with metadata."""
    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    help_text: str = ""
    metric_type: str = "gauge"  # gauge, counter, histogram

    @property
    def full_name(self) -> str:
        return f"icyquant_{self.name}"

    def to_prometheus(self) -> str:
        """Render in Prometheus text format."""
        label_str = ""
        if self.labels:
            label_pairs = [f'{k}="{v}"' for k, v in self.labels.items()]
            label_str = "{" + ",".join(label_pairs) + "}"

        lines = []
        if self.help_text:
            lines.append(f"# HELP {self.full_name} {self.help_text}")
            lines.append(f"# TYPE {self.full_name} {self.metric_type}")
        lines.append(f"{self.full_name}{label_str} {self.value}")
        return "\n".join(lines)


class StrategyMetrics:
    """Collector for strategy platform metrics.

    Tracks all operational metrics in a Prometheus-compatible format.
    Metrics are updated atomically via a lock.

    Usage:
        metrics = StrategyMetrics()

        # Record events
        metrics.inc("strategy_deploy_total", {"result": "success"})
        metrics.set("strategy_running", 5)

        # Export
        prom_text = metrics.export_prometheus()
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._counters: Dict[str, Dict[str, float]] = {}  # name → label_key → value
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}

        self._registry: Dict[str, Metric] = {}
        self._register_defaults()
        logger.info("StrategyMetrics initialized")

    def _register_defaults(self) -> None:
        """Register default strategy metrics."""
        defaults = [
            Metric("strategy_total", 0, help_text="Total strategies registered", metric_type="gauge"),
            Metric("strategy_running", 0, help_text="Currently running strategies", metric_type="gauge"),
            Metric("strategy_deploy_total", 0, help_text="Total strategy deployments", metric_type="counter"),
            Metric("strategy_restart_total", 0, help_text="Total strategy restarts", metric_type="counter"),
            Metric("strategy_snapshot_total", 0, help_text="Total snapshots taken", metric_type="counter"),
            Metric("strategy_recovery_total", 0, help_text="Total recovery attempts", metric_type="counter"),
            Metric("strategy_recovery_success", 0, help_text="Successful recoveries", metric_type="counter"),
            Metric("strategy_recovery_failure", 0, help_text="Failed recoveries", metric_type="counter"),
            Metric("strategy_duration_ms", 0, help_text="Strategy execution duration", metric_type="gauge"),
        ]
        for m in defaults:
            self._registry[m.name] = m

    # ── Counter Operations ──

    def inc(self, name: str, labels: Optional[Dict[str, str]] = None, amount: float = 1.0) -> None:
        """Increment a counter metric."""
        label_key = _label_key(labels)
        with self._lock:
            self._counters.setdefault(name, {})
            self._counters[name][label_key] = self._counters[name].get(label_key, 0) + amount

        # Also update the base gauge
        if name in self._registry:
            with self._lock:
                self._registry[name].value = self._counters[name].get(label_key, 0)

    def dec(self, name: str, labels: Optional[Dict[str, str]] = None, amount: float = 1.0) -> None:
        """Decrement a metric."""
        self.inc(name, labels, -amount)

    # ── Gauge Operations ──

    def set(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric to an absolute value."""
        with self._lock:
            self._gauges[name] = value
            if name in self._registry:
                self._registry[name].value = value
                if labels:
                    self._registry[name].labels = labels

    def observe(self, name: str, value: float) -> None:
        """Record an observation for a histogram metric."""
        with self._lock:
            self._histograms.setdefault(name, []).append(value)

    # ── Snapshot ──

    def snapshot_metrics(self) -> Dict[str, Any]:
        """Return all current metric values."""
        with self._lock:
            result: Dict[str, Any] = {}
            for name, m in self._registry.items():
                result[name] = {
                    "value": m.value,
                    "type": m.metric_type,
                    "help": m.help_text,
                    "labels": m.labels,
                }
            # Include counters
            for name, counters in self._counters.items():
                for label_key, val in counters.items():
                    key = f"{name}[{label_key}]"
                    result[key] = {"value": val, "type": "counter"}
            return result

    def export_prometheus(self) -> str:
        """Export all metrics in Prometheus text format."""
        lines: List[str] = []
        with self._lock:
            # Registered metrics
            for m in self._registry.values():
                if m.value != 0 or m.metric_type == "gauge":
                    lines.append(m.to_prometheus())

            # Counters with labels
            for name, counters in self._counters.items():
                for label_key, val in counters.items():
                    if label_key == "__default__":
                        continue
                    labels = _parse_label_key(label_key)
                    m = Metric(name=name, value=val, labels=labels,
                              help_text=self._registry[name].help_text if name in self._registry else "",
                              metric_type="counter")
                    lines.append(m.to_prometheus())

            # Histograms
            for name, values in self._histograms.items():
                if not values:
                    continue
                sorted_vals = sorted(values)
                lines.append(f"# HELP icyquant_{name} {name}")
                lines.append(f"# TYPE icyquant_{name} histogram")
                lines.append(f'icyquant_{name}_count {len(values)}')
                lines.append(f'icyquant_{name}_sum {sum(values)}')

        return "\n".join(lines)

    def reset(self) -> None:
        """Reset all metrics to zero."""
        with self._lock:
            for m in self._registry.values():
                m.value = 0
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._register_defaults()


def _label_key(labels: Optional[Dict[str, str]]) -> str:
    """Convert labels dict to a stable string key."""
    if not labels:
        return "__default__"
    return "|".join(f"{k}={v}" for k, v in sorted(labels.items()))


def _parse_label_key(key: str) -> Dict[str, str]:
    """Parse label key back to dict."""
    if key == "__default__":
        return {}
    labels = {}
    for part in key.split("|"):
        if "=" in part:
            k, v = part.split("=", 1)
            labels[k] = v
    return labels
