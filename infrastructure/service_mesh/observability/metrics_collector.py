"""Metrics collector for ICYQuant Service Mesh.

Provides ``MeshMetricsCollector`` for collecting traffic, latency,
error, retry, connection, and policy metrics, with Prometheus-
compatible output.
"""

from __future__ import annotations

import logging
import threading
import time
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class MetricType(str, Enum):
    """Metric types."""

    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


class MetricPoint:
    """A single metric data point."""

    def __init__(
        self,
        name: str,
        value: float,
        mtype: MetricType = MetricType.GAUGE,
        labels: Optional[Dict[str, str]] = None,
        timestamp: Optional[datetime] = None,
    ) -> None:
        self.name = name
        self.value = value
        self.mtype = mtype
        self.labels = labels or {}
        self.timestamp = timestamp or datetime.utcnow()

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "type": self.mtype.value,
            "labels": dict(self.labels),
            "timestamp": self.timestamp.isoformat(),
        }


class MeshMetricsCollector:
    """Collects mesh metrics across services."""

    def __init__(self, max_points: int = 100000) -> None:
        self._lock = threading.RLock()
        self._max_points = max_points
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._labelled_counters: Dict[str, Dict[str, float]] = {}
        self._labelled_gauges: Dict[str, Dict[str, float]] = {}
        self._points: List[MetricPoint] = []
        self._collection_count = 0
        self._flush_count = 0
        self._started = False

    @property
    def is_running(self) -> bool:
        return self._started

    def start(self) -> None:
        self._started = True
        logger.info("Mesh metrics collector started")

    def stop(self) -> None:
        self._started = False
        logger.info("Mesh metrics collector stopped")

    def increment(
        self,
        name: str,
        value: float = 1.0,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        with self._lock:
            self._collection_count += 1
            if labels:
                key = self._labels_key(labels)
                if name not in self._labelled_counters:
                    self._labelled_counters[name] = {}
                if key not in self._labelled_counters[name]:
                    self._labelled_counters[name][key] = 0.0
                self._labelled_counters[name][key] += value
            else:
                if name not in self._counters:
                    self._counters[name] = 0.0
                self._counters[name] += value

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        with self._lock:
            self._collection_count += 1
            if labels:
                key = self._labels_key(labels)
                if name not in self._labelled_gauges:
                    self._labelled_gauges[name] = {}
                self._labelled_gauges[name][key] = value
            else:
                self._gauges[name] = value

    def observe(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        with self._lock:
            self._collection_count += 1
            if name not in self._histograms:
                self._histograms[name] = []
            self._histograms[name].append(value)
            if len(self._histograms[name]) > 10000:
                self._histograms[name] = self._histograms[name][-10000:]

    def record_traffic(self, service: str, count: int = 1) -> None:
        self.increment("mesh_traffic_total", count, {"service": service})

    def record_latency(self, service: str, latency_ms: float) -> None:
        self.observe("mesh_latency_ms", latency_ms, {"service": service})

    def record_error(self, service: str, error_type: str = "") -> None:
        self.increment("mesh_errors_total", 1, {"service": service, "type": error_type})

    def record_retry(self, service: str, count: int = 1) -> None:
        self.increment("mesh_retries_total", count, {"service": service})

    def record_connection(self, service: str, active: int) -> None:
        self.set_gauge("mesh_connections_active", active, {"service": service})

    def record_policy_eval(self, policy_id: str, result: str) -> None:
        self.increment("mesh_policy_eval_total", 1, {"policy_id": policy_id, "result": result})

    def _labels_key(self, labels: Dict[str, str]) -> str:
        return ",".join(f"{k}={v}" for k, v in sorted(labels.items()))

    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        with self._lock:
            if labels:
                key = self._labels_key(labels)
                return self._labelled_counters.get(name, {}).get(key, 0.0)
            return self._counters.get(name, 0.0)

    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        with self._lock:
            if labels:
                key = self._labels_key(labels)
                return self._labelled_gauges.get(name, {}).get(key, 0.0)
            return self._gauges.get(name, 0.0)

    def get_histogram(
        self,
        name: str,
        percentiles: Optional[List[float]] = None,
    ) -> Dict[str, Any]:
        with self._lock:
            values = list(self._histograms.get(name, []))
        if not values:
            return {"count": 0, "min": 0, "max": 0, "avg": 0}
        result = {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
        }
        if percentiles:
            for p in percentiles:
                result[f"p{int(p)}"] = _percentile(values, p)
        return result

    def collect(self) -> List[MetricPoint]:
        """Collect all current metric values as points."""
        points: List[MetricPoint] = []
        with self._lock:
            for name, value in self._counters.items():
                points.append(MetricPoint(name, value, MetricType.COUNTER))
            for name, value in self._gauges.items():
                points.append(MetricPoint(name, value, MetricType.GAUGE))
            for name, labelled in self._labelled_counters.items():
                for key, value in labelled.items():
                    labels = self._parse_key(key)
                    points.append(
                        MetricPoint(name, value, MetricType.COUNTER, labels)
                    )
            for name, labelled in self._labelled_gauges.items():
                for key, value in labelled.items():
                    labels = self._parse_key(key)
                    points.append(
                        MetricPoint(name, value, MetricType.GAUGE, labels)
                    )
            self._points.extend(points)
            if len(self._points) > self._max_points:
                self._points = self._points[-self._max_points:]
        return points

    def _parse_key(self, key: str) -> Dict[str, str]:
        labels: Dict[str, str] = {}
        for pair in key.split(","):
            if "=" in pair:
                k, v = pair.split("=", 1)
                labels[k] = v
        return labels

    def flush(self) -> Dict[str, Any]:
        points = self.collect()
        with self._lock:
            self._flush_count += 1
        return {
            "flushed": len(points),
            "flush_count": self._flush_count,
        }

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus text format."""
        lines: List[str] = []
        with self._lock:
            for name, value in self._counters.items():
                lines.append(f"# TYPE {name} counter")
                lines.append(f"{name} {value}")
            for name, value in self._gauges.items():
                lines.append(f"# TYPE {name} gauge")
                lines.append(f"{name} {value}")
            for name, labelled in self._labelled_counters.items():
                lines.append(f"# TYPE {name} counter")
                for key, value in labelled.items():
                    labels = self._parse_key(key)
                    label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
                    lines.append(f"{name}{{{label_str}}} {value}")
            for name, labelled in self._labelled_gauges.items():
                lines.append(f"# TYPE {name} gauge")
                for key, value in labelled.items():
                    labels = self._parse_key(key)
                    label_str = ",".join(f'{k}="{v}"' for k, v in labels.items())
                    lines.append(f"{name}{{{label_str}}} {value}")
            for name, values in self._histograms.items():
                lines.append(f"# TYPE {name} histogram")
                if values:
                    lines.append(f"{name}_count {len(values)}")
                    lines.append(f"{name}_sum {sum(values)}")
        return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "running": self._started,
                "counter_count": len(self._counters),
                "gauge_count": len(self._gauges),
                "histogram_count": len(self._histograms),
                "labelled_counter_count": sum(
                    len(v) for v in self._labelled_counters.values()
                ),
                "labelled_gauge_count": sum(
                    len(v) for v in self._labelled_gauges.values()
                ),
                "collection_count": self._collection_count,
                "flush_count": self._flush_count,
                "stored_points": len(self._points),
            }

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._labelled_counters.clear()
            self._labelled_gauges.clear()
            self._points.clear()


def _percentile(values: List[float], p: float) -> float:
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * p / 100.0
    f = int(k)
    c = min(f + 1, len(sorted_vals) - 1)
    if f == c:
        return sorted_vals[f]
    return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)
