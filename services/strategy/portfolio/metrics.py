"""
Portfolio Decision Metrics
==========================
Prometheus-compatible metrics for the portfolio decision and order intent subsystems.

Part of Commit 13 Part 1.3: Portfolio Decision.

Metrics:
    icyquant_position_sizing_total     — Counter
    icyquant_order_intent_total        — Counter
    icyquant_order_netting_total       — Counter
    icyquant_strategy_conflict_total   — Counter
    icyquant_capital_allocation_total  — Counter
    icyquant_portfolio_decision_latency — Histogram
    icyquant_exposure_limit_hits       — Counter
"""

from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

@dataclass
class Metric:
    """A single metric data point."""

    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_prometheus(self) -> str:
        label_str = ""
        if self.labels:
            label_parts = [f'{k}="{v}"' for k, v in self.labels.items()]
            label_str = "{" + ",".join(label_parts) + "}"
        return f"{self.name}{label_str} {self.value}"


# ---------------------------------------------------------------------------
# Portfolio Decision Metrics
# ---------------------------------------------------------------------------

class PortfolioDecisionMetrics:
    """Combined metrics collector for portfolio decision and order intent subsystems."""

    def __init__(self):
        # Counters
        self._counters: Dict[str, float] = defaultdict(float)

        # Gauges
        self._gauges: Dict[str, float] = {}

        # Histograms
        self._histograms: Dict[str, List[float]] = defaultdict(list)

        # Timers
        self._timers: Dict[str, float] = {}

    # ------------------------------------------------------------------
    # Counter Operations
    # ------------------------------------------------------------------

    def inc(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        key = self._metric_key(name, labels)
        self._counters[key] += value

    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        key = self._metric_key(name, labels)
        return self._counters.get(key, 0.0)

    # ------------------------------------------------------------------
    # Gauge Operations
    # ------------------------------------------------------------------

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        key = self._metric_key(name, labels)
        self._gauges[key] = value

    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> Optional[float]:
        key = self._metric_key(name, labels)
        return self._gauges.get(key)

    # ------------------------------------------------------------------
    # Histogram Operations
    # ------------------------------------------------------------------

    def observe(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        key = self._metric_key(name, labels)
        self._histograms[key].append(value)
        if len(self._histograms[key]) > 10000:
            self._histograms[key] = self._histograms[key][-5000:]

    def get_histogram_stats(
        self, name: str, labels: Optional[Dict[str, str]] = None
    ) -> Dict[str, float]:
        key = self._metric_key(name, labels)
        values = self._histograms.get(key, [])
        if not values:
            return {
                "count": 0, "sum": 0, "min": 0, "max": 0,
                "avg": 0, "p50": 0, "p95": 0, "p99": 0,
            }

        sorted_vals = sorted(values)
        n = len(sorted_vals)
        return {
            "count": n,
            "sum": sum(sorted_vals),
            "min": sorted_vals[0],
            "max": sorted_vals[-1],
            "avg": sum(sorted_vals) / n,
            "p50": sorted_vals[int(n * 0.50)],
            "p95": sorted_vals[int(n * 0.95)],
            "p99": sorted_vals[int(n * 0.99)],
        }

    # ------------------------------------------------------------------
    # Timer
    # ------------------------------------------------------------------

    def start_timer(self, name: str) -> None:
        self._timers[name] = time.monotonic()

    def stop_timer(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        start = self._timers.pop(name, None)
        if start is None:
            return 0.0
        duration = time.monotonic() - start
        self.observe(name, duration, labels)
        return duration

    # ------------------------------------------------------------------
    # Built-in Metrics — Counter
    # ------------------------------------------------------------------

    def record_position_sizing(
        self, strategy_id: str = "", model: str = "", count: int = 1
    ) -> None:
        """Record position sizing operations."""
        self.inc(
            "icyquant_position_sizing_total",
            count,
            {"strategy": strategy_id, "model": model},
        )

    def record_order_intent(
        self, portfolio_id: str = "", side: str = "", count: int = 1
    ) -> None:
        """Record order intent creation."""
        self.inc(
            "icyquant_order_intent_total",
            count,
            {"portfolio": portfolio_id, "side": side},
        )

    def record_order_netting(self, count: int = 1) -> None:
        """Record netting operations."""
        self.inc("icyquant_order_netting_total", count)

    def record_strategy_conflict(self, conflict_type: str = "") -> None:
        """Record cross-strategy conflict detections."""
        self.inc(
            "icyquant_strategy_conflict_total",
            labels={"type": conflict_type},
        )

    def record_capital_allocation(
        self, portfolio_id: str = "", policy: str = "", count: int = 1
    ) -> None:
        """Record capital allocation operations."""
        self.inc(
            "icyquant_capital_allocation_total",
            count,
            {"portfolio": portfolio_id, "policy": policy},
        )

    def record_exposure_limit_hit(self, exposure_type: str = "") -> None:
        """Record exposure limit breaches."""
        self.inc(
            "icyquant_exposure_limit_hits",
            labels={"exposure_type": exposure_type},
        )

    # ------------------------------------------------------------------
    # Built-in Metrics — Histogram
    # ------------------------------------------------------------------

    def record_portfolio_decision_latency(
        self, duration_seconds: float, stage: str = ""
    ) -> None:
        """Record portfolio decision pipeline latency."""
        self.observe(
            "icyquant_portfolio_decision_latency",
            duration_seconds,
            {"stage": stage},
        )

    # ------------------------------------------------------------------
    # Built-in Metrics — Gauge
    # ------------------------------------------------------------------

    def record_exposure(
        self, exposure_type: str, value: float, portfolio_id: str = ""
    ) -> None:
        """Record current exposure levels."""
        self.set_gauge(
            f"icyquant_exposure_{exposure_type}",
            value,
            {"portfolio": portfolio_id},
        )

    def record_leverage(self, value: float, portfolio_id: str = "") -> None:
        """Record current leverage ratio."""
        self.set_gauge(
            "icyquant_leverage_ratio",
            value,
            {"portfolio": portfolio_id},
        )

    def record_allocated_capital(self, value: float, portfolio_id: str = "") -> None:
        """Record currently allocated capital."""
        self.set_gauge(
            "icyquant_allocated_capital",
            value,
            {"portfolio": portfolio_id},
        )

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_prometheus(self) -> str:
        """Export all metrics in Prometheus text format."""
        lines = []

        for key, value in self._counters.items():
            name, labels = self._parse_key(key)
            metric = Metric(name=name, value=value, labels=labels)
            lines.append(f"# TYPE {name} counter")
            lines.append(metric.to_prometheus())

        for key, value in self._gauges.items():
            name, labels = self._parse_key(key)
            metric = Metric(name=name, value=value, labels=labels)
            lines.append(f"# TYPE {name} gauge")
            lines.append(metric.to_prometheus())

        for key, values in self._histograms.items():
            name, labels = self._parse_key(key)
            stats = self.get_histogram_stats(name, labels)
            lines.append(f"# TYPE {name} histogram")
            for stat_name, stat_val in stats.items():
                lines.append(f"{name}_{stat_name} {stat_val}")

        return "\n".join(lines)

    def snapshot(self) -> Dict[str, Any]:
        """Return a JSON-serializable metrics snapshot."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "histogram_names": list(self._histograms.keys()),
            "histogram_count": sum(len(v) for v in self._histograms.values()),
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._timers.clear()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _metric_key(name: str, labels: Optional[Dict[str, str]] = None) -> str:
        if not labels:
            return name
        label_str = ",".join(f"{k}={v}" for k, v in sorted(labels.items()))
        return f"{name}[{label_str}]"

    @staticmethod
    def _parse_key(key: str) -> tuple:
        if "[" not in key:
            return key, {}
        name, label_part = key.split("[", 1)
        label_part = label_part.rstrip("]")
        labels = {}
        for pair in label_part.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                labels[k] = v
        return name, labels
