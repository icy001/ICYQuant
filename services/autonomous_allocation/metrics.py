"""Allocation Metrics — Prometheus-format metrics for autonomous allocation.

Exposes 24+ gauges and counters tracking every dimension
of the autonomous allocation pipeline.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class MetricType(str, Enum):
    """Metric types."""
    GAUGE = "GAUGE"
    COUNTER = "COUNTER"
    HISTOGRAM = "HISTOGRAM"


@dataclass
class MetricValue:
    """A single metric value."""
    name: str
    value: float = 0.0
    labels: Dict[str, str] = field(default_factory=dict)
    metric_type: MetricType = MetricType.GAUGE
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class MetricsSnapshot:
    """Snapshot of all allocation metrics."""
    metrics: Dict[str, MetricValue] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)

    def to_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines = []
        for metric in self.metrics.values():
            label_str = ""
            if metric.labels:
                label_str = "{" + ",".join(
                    f'{k}="{v}"' for k, v in metric.labels.items()
                ) + "}"
            suffix = ""
            if metric.metric_type == MetricType.COUNTER:
                suffix = "_total"
            lines.append(
                f"icyquant_{metric.name}{suffix}{label_str} {metric.value}"
            )
        return "\n".join(lines)


class AllocationMetrics:
    """Collects and exposes Prometheus-format allocation metrics.

    Metrics tracked:
    - Allocation scores per strategy
    - Capital allocation amounts
    - Target allocations and deltas
    - Marginal alpha/risk/cost/capacity/survival
    - Risk-adjusted capital efficiency
    - Strategy rankings
    - Reserve and buffer ratios
    - Rebalance indicators
    - Guard rejections/resizes/freezes
    - Prediction errors
    - Feedback event counts
    """

    def __init__(self):
        self._metrics: Dict[str, MetricValue] = {}
        self._counters: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._initialize_gauges()
        self._initialize_counters()

    def _initialize_gauges(self) -> None:
        """Initialize all gauge metrics."""
        gauges = [
            "allocation_score",
            "capital_allocation",
            "target_allocation",
            "allocation_delta",
            "marginal_alpha",
            "marginal_risk",
            "marginal_cost",
            "marginal_capacity",
            "marginal_survival",
            "risk_adjusted_capital_efficiency",
            "strategy_rank",
            "strategy_weight",
            "capital_reserve",
            "capital_buffer",
            "rebalance_required",
            "rebalance_delta",
            "rebalance_priority",
            "autonomy_level",
            "allocation_prediction_error",
        ]
        for name in gauges:
            self._metrics[name] = MetricValue(name=name, metric_type=MetricType.GAUGE)

    def _initialize_counters(self) -> None:
        """Initialize counter metrics."""
        counters = [
            "strategy_rotation",
            "allocation_rejections",
            "allocation_resizes",
            "allocation_freezes",
            "allocation_feedback_events",
        ]
        for name in counters:
            self._counters[name] = 0.0
            self._metrics[name] = MetricValue(name=name, metric_type=MetricType.COUNTER)

    def set_gauge(self, name: str, value: float,
                  labels: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric value."""
        if name in self._metrics:
            self._metrics[name].value = value
            if labels:
                self._metrics[name].labels = labels
        else:
            self._metrics[name] = MetricValue(
                name=name, value=value, labels=labels or {},
                metric_type=MetricType.GAUGE,
            )

    def increment_counter(self, name: str, delta: float = 1.0) -> None:
        """Increment a counter metric."""
        if name in self._counters:
            self._counters[name] += delta
            self._metrics[name].value = self._counters[name]
        else:
            self._counters[name] = delta
            self._metrics[name] = MetricValue(
                name=name, value=delta, metric_type=MetricType.COUNTER,
            )

    def record_histogram(self, name: str, value: float) -> None:
        """Record a histogram value."""
        if name not in self._histograms:
            self._histograms[name] = []
        self._histograms[name].append(value)
        if len(self._histograms[name]) > 10000:
            self._histograms[name] = self._histograms[name][-10000:]

    def record_allocation_score(self, strategy_id: str,
                                score: float, **sub_scores) -> None:
        """Record allocation score for a strategy."""
        self.set_gauge("allocation_score", score, {"strategy": strategy_id})
        for key, val in sub_scores.items():
            self.set_gauge(f"allocation_score_{key}", val, {"strategy": strategy_id})

    def record_capital_allocation(self, strategy_id: str,
                                   capital: float, target: float,
                                   delta: float) -> None:
        """Record capital allocation metrics."""
        self.set_gauge("capital_allocation", capital, {"strategy": strategy_id})
        self.set_gauge("target_allocation", target, {"strategy": strategy_id})
        self.set_gauge("allocation_delta", delta, {"strategy": strategy_id})

    def record_marginal(self, strategy_id: str,
                        marginal_alpha: float = 0.0,
                        marginal_risk: float = 0.0,
                        marginal_cost: float = 0.0,
                        marginal_capacity: float = 0.0,
                        marginal_survival: float = 0.0,
                        ramce: float = 0.0) -> None:
        """Record marginal analysis metrics."""
        labels = {"strategy": strategy_id}
        self.set_gauge("marginal_alpha", marginal_alpha, labels)
        self.set_gauge("marginal_risk", marginal_risk, labels)
        self.set_gauge("marginal_cost", marginal_cost, labels)
        self.set_gauge("marginal_capacity", marginal_capacity, labels)
        self.set_gauge("marginal_survival", marginal_survival, labels)
        self.set_gauge("risk_adjusted_capital_efficiency", ramce, labels)

    def record_rebalance(self, required: float = 0.0,
                          delta: float = 0.0,
                          priority: float = 0.0) -> None:
        """Record rebalance metrics."""
        self.set_gauge("rebalance_required", required)
        self.set_gauge("rebalance_delta", delta)
        self.set_gauge("rebalance_priority", priority)

    def record_guard_action(self, result: str) -> None:
        """Record guard action result."""
        if result == "REJECTED":
            self.increment_counter("allocation_rejections")
        elif result == "RESIZE_REQUIRED":
            self.increment_counter("allocation_resizes")
        elif result == "DEFERRED":
            self.increment_counter("allocation_freezes")

    def record_prediction_error(self, metric: str, error: float) -> None:
        """Record a prediction error."""
        self.set_gauge("allocation_prediction_error", error, {"metric": metric})

    def record_feedback(self) -> None:
        """Record a feedback event."""
        self.increment_counter("allocation_feedback_events")

    def record_autonomy_level(self, level: int) -> None:
        """Record current autonomy level."""
        self.set_gauge("autonomy_level", float(level))

    def snapshot(self) -> MetricsSnapshot:
        """Take a snapshot of all current metrics."""
        return MetricsSnapshot(
            metrics=dict(self._metrics),
            timestamp=datetime.utcnow(),
        )

    def get_all(self) -> Dict[str, float]:
        """Get all metric name-value pairs."""
        return {name: m.value for name, m in self._metrics.items()}

    def reset_counters(self) -> None:
        """Reset all counters to zero."""
        for name in self._counters:
            self._counters[name] = 0.0
            if name in self._metrics:
                self._metrics[name].value = 0.0
