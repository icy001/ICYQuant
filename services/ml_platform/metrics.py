"""
ICYQuant ML Platform Metrics - Prometheus metrics for ML operations.

Exposes metrics for monitoring the ML platform:

    icyquant_features_total
    icyquant_feature_computation_latency
    icyquant_feature_quality_score
    icyquant_training_datasets_total
    icyquant_training_runs_total
    icyquant_experiments_total
    icyquant_model_versions_total
    icyquant_model_evaluations_total
    icyquant_feature_drift_total
    icyquant_prediction_drift_total
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Metric Collector (in-memory, no external deps)
# ---------------------------------------------------------------------------


@dataclass
class MetricValue:
    """A single metric value."""

    name: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class MLMetricsCollector:
    """Collects and exposes ML platform metrics.

    Simulates Prometheus client library metrics without requiring
    the actual dependency. In production, replace with prometheus_client.
    """

    def __init__(self) -> None:
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._history: List[MetricValue] = []

    # -- Counters --

    def inc_counter(self, name: str, value: float = 1.0, labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric."""
        key = self._metric_key(name, labels)
        self._counters[key] = self._counters.get(key, 0.0) + value
        self._record(name, self._counters[key], labels)

    def get_counter(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get counter value."""
        return self._counters.get(self._metric_key(name, labels), 0.0)

    # -- Gauges --

    def set_gauge(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric."""
        key = self._metric_key(name, labels)
        self._gauges[key] = value
        self._record(name, value, labels)

    def get_gauge(self, name: str, labels: Optional[Dict[str, str]] = None) -> float:
        """Get gauge value."""
        return self._gauges.get(self._metric_key(name, labels), 0.0)

    # -- Histograms --

    def observe(self, name: str, value: float, labels: Optional[Dict[str, str]] = None) -> None:
        """Record a histogram observation."""
        key = self._metric_key(name, labels)
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)
        self._record(name, value, labels)

    def get_histogram_stats(self, name: str, labels: Optional[Dict[str, str]] = None) -> Dict[str, float]:
        """Get histogram statistics."""
        key = self._metric_key(name, labels)
        values = self._histograms.get(key, [])
        if not values:
            return {"count": 0, "sum": 0, "min": 0, "max": 0, "avg": 0}
        return {
            "count": len(values),
            "sum": sum(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "p50": sorted(values)[len(values)//2],
            "p95": sorted(values)[int(len(values)*0.95)],
            "p99": sorted(values)[int(len(values)*0.99)],
        }

    # -- Helpers --

    def _metric_key(self, name: str, labels: Optional[Dict[str, str]] = None) -> str:
        """Build a unique key from name and labels."""
        if not labels:
            return name
        sorted_labels = sorted(labels.items())
        label_str = ",".join(f"{k}={v}" for k, v in sorted_labels)
        return f"{name}{{{label_str}}}"

    def _record(self, name: str, value: float, labels: Optional[Dict[str, str]]) -> None:
        """Record a metric value in history."""
        self._history.append(MetricValue(
            name=name, value=value, labels=labels or {},
        ))

    # -- Snapshot --

    def snapshot(self) -> Dict[str, Any]:
        """Get a snapshot of all current metric values."""
        return {
            "counters": dict(self._counters),
            "gauges": dict(self._gauges),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def clear(self) -> None:
        """Clear all metrics."""
        self._counters.clear()
        self._gauges.clear()
        self._histograms.clear()
        self._history.clear()


# ---------------------------------------------------------------------------
# Pre-defined ML Metrics
# ---------------------------------------------------------------------------


# Global metrics collector
_metrics = MLMetricsCollector()


def get_metrics() -> MLMetricsCollector:
    """Get the global metrics collector."""
    return _metrics


def record_feature_computed(feature_id: str, latency_seconds: float) -> None:
    """Record a feature computation."""
    _metrics.inc_counter("icyquant_features_total", labels={"feature_id": feature_id})
    _metrics.observe("icyquant_feature_computation_latency", latency_seconds)


def record_dataset_created(dataset_id: str) -> None:
    """Record a training dataset creation."""
    _metrics.inc_counter("icyquant_training_datasets_total", labels={"dataset_id": dataset_id})


def record_experiment_run(experiment_id: str, status: str = "completed") -> None:
    """Record an experiment run."""
    _metrics.inc_counter("icyquant_experiments_total", labels={"status": status})


def record_training_run(run_id: str, model_type: str, duration_seconds: float) -> None:
    """Record a training run."""
    _metrics.inc_counter("icyquant_training_runs_total", labels={"model_type": model_type})
    _metrics.observe("icyquant_training_duration", duration_seconds)


def record_model_version(model_id: str) -> None:
    """Record a new model version."""
    _metrics.inc_counter("icyquant_model_versions_total", labels={"model_id": model_id})


def record_model_evaluation(model_id: str, ic: float, rank_ic: float) -> None:
    """Record a model evaluation."""
    _metrics.inc_counter("icyquant_model_evaluations_total")
    _metrics.set_gauge("icyquant_model_ic", ic, labels={"model_id": model_id})
    _metrics.set_gauge("icyquant_model_rank_ic", rank_ic, labels={"model_id": model_id})


def record_feature_drift(feature_id: str, drift_score: float) -> None:
    """Record feature drift detection."""
    _metrics.inc_counter("icyquant_feature_drift_total")
    _metrics.set_gauge("icyquant_feature_drift_score", drift_score, labels={"feature_id": feature_id})


def record_prediction_drift(model_id: str, drift_score: float) -> None:
    """Record prediction drift."""
    _metrics.inc_counter("icyquant_prediction_drift_total")
    _metrics.set_gauge("icyquant_prediction_drift_score", drift_score, labels={"model_id": model_id})


def record_feature_quality(feature_id: str, quality_score: float) -> None:
    """Record feature quality score."""
    _metrics.set_gauge("icyquant_feature_quality_score", quality_score, labels={"feature_id": feature_id})
