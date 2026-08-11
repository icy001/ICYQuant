"""
Alpha & Signal Metrics — Prometheus metrics for alpha and signal subsystems.

Part of Commit 13 Part 1.2: Signal & Alpha Engine.

Metrics:
    icyquant_alpha_generated_total    — Counter
    icyquant_signal_generated_total   — Counter
    icyquant_signal_validation_failed — Counter
    icyquant_signal_confidence        — Histogram
    icyquant_alpha_decay_total        — Counter
    icyquant_signal_latency           — Histogram
    icyquant_signal_rank_duration     — Histogram
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
# Alpha Signal Metrics
# ---------------------------------------------------------------------------

class AlphaSignalMetrics:
    """Combined metrics collector for alpha and signal subsystems."""

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

    def get_histogram_stats(self, name: str, labels: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        key = self._metric_key(name, labels)
        values = self._histograms.get(key, [])
        if not values:
            return {"count": 0, "sum": 0, "min": 0, "max": 0, "avg": 0, "p50": 0, "p95": 0, "p99": 0}

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
    # Built-in Metrics
    # ------------------------------------------------------------------

    def record_alpha_generated(self, alpha_id: str = "", count: int = 1) -> None:
        self.inc("icyquant_alpha_generated_total", count, {"alpha": alpha_id})

    def record_signal_generated(self, strategy_id: str = "", count: int = 1) -> None:
        self.inc("icyquant_signal_generated_total", count, {"strategy": strategy_id})

    def record_validation_failed(self, reason: str = "") -> None:
        self.inc("icyquant_signal_validation_failed", labels={"reason": reason})

    def record_confidence(self, confidence: float) -> None:
        self.observe("icyquant_signal_confidence", confidence)

    def record_alpha_decay(self, alpha_id: str = "") -> None:
        self.inc("icyquant_alpha_decay_total", labels={"alpha": alpha_id})

    def record_signal_latency(self, duration_seconds: float, stage: str = "") -> None:
        self.observe("icyquant_signal_latency", duration_seconds, {"stage": stage})

    def record_rank_duration(self, duration_seconds: float) -> None:
        self.observe("icyquant_signal_rank_duration", duration_seconds)

    # ------------------------------------------------------------------
    # Export
    # ------------------------------------------------------------------

    def export_prometheus(self) -> str:
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

    def reset(self) -> None:
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
