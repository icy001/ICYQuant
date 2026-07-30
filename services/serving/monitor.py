"""Inference Monitor — real-time serving health and performance tracking.

Monitors latency, QPS, error rate, prediction drift, and cache hit rate
for the model serving layer. Integrates with the platform monitoring center.

Usage::

    monitor = InferenceMonitor(config=MonitorConfig())
    monitor.record_latency(12.5)  # ms
    monitor.record_prediction(0.82)
    stats = monitor.get_stats()
"""

from __future__ import annotations

import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional


class HealthStatus(str, Enum):
    """Serving health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


@dataclass
class LatencyMetric:
    """Latency statistics.

    Attributes:
        avg_ms: Average latency.
        p50_ms: 50th percentile (median).
        p95_ms: 95th percentile.
        p99_ms: 99th percentile.
        max_ms: Maximum observed latency.
        min_ms: Minimum observed latency.
        count: Number of samples.
    """

    avg_ms: float = 0.0
    p50_ms: float = 0.0
    p95_ms: float = 0.0
    p99_ms: float = 0.0
    max_ms: float = 0.0
    min_ms: float = 0.0
    count: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "avg_ms": round(self.avg_ms, 3),
            "p50_ms": round(self.p50_ms, 3),
            "p95_ms": round(self.p95_ms, 3),
            "p99_ms": round(self.p99_ms, 3),
            "max_ms": round(self.max_ms, 3),
            "min_ms": round(self.min_ms, 3),
            "count": self.count,
        }


@dataclass
class QPSMetric:
    """Queries-per-second statistics.

    Attributes:
        current_qps: Current QPS (recent window).
        peak_qps: Peak observed QPS.
        avg_qps: Average QPS since start.
        total_requests: Total requests served.
        window_seconds: Observation window for current_qps.
    """

    current_qps: float = 0.0
    peak_qps: float = 0.0
    avg_qps: float = 0.0
    total_requests: int = 0
    window_seconds: float = 60.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "current_qps": round(self.current_qps, 1),
            "peak_qps": round(self.peak_qps, 1),
            "avg_qps": round(self.avg_qps, 1),
            "total_requests": self.total_requests,
            "window_seconds": self.window_seconds,
        }


@dataclass
class DriftMetric:
    """Prediction/data drift detection metrics.

    Attributes:
        prediction_mean: Current mean prediction.
        prediction_std: Current prediction std dev.
        historical_mean: Historical mean (baseline).
        historical_std: Historical std dev (baseline).
        psi: Population Stability Index.
        drift_detected: Whether drift threshold exceeded.
    """

    prediction_mean: float = 0.0
    prediction_std: float = 0.0
    historical_mean: float = 0.0
    historical_std: float = 0.0
    psi: float = 0.0
    drift_detected: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "prediction_mean": round(self.prediction_mean, 4),
            "prediction_std": round(self.prediction_std, 4),
            "historical_mean": round(self.historical_mean, 4),
            "historical_std": round(self.historical_std, 4),
            "psi": round(self.psi, 4),
            "drift_detected": self.drift_detected,
        }


@dataclass
class MonitorConfig:
    """Inference monitor configuration.

    Attributes:
        latency_window_size: Max samples for latency tracking.
        qps_window_seconds: Window for QPS calculation.
        drift_window_size: Max samples for drift calculation.
        drift_threshold_psi: PSI threshold for drift alert.
        error_rate_threshold: Error rate threshold.
        latency_p99_threshold_ms: P99 latency threshold.
        enable_alerts: Whether to trigger alert callbacks.
    """

    latency_window_size: int = 10000
    qps_window_seconds: float = 60.0
    drift_window_size: int = 5000
    drift_threshold_psi: float = 0.1
    error_rate_threshold: float = 0.01
    latency_p99_threshold_ms: float = 100.0
    enable_alerts: bool = True


class InferenceMonitor:
    """Real-time inference monitoring and health tracking.

    Tracks latency, QPS, errors, prediction drift, and cache performance.
    Supports health checks and alert callbacks.

    Usage::

        monitor = InferenceMonitor(config=MonitorConfig())
        monitor.record_latency(12.5)
        monitor.record_prediction(0.82)
        monitor.record_error()
        stats = monitor.get_stats()
        health = monitor.check_health()
    """

    def __init__(self, config: Optional[MonitorConfig] = None):
        self.config = config or MonitorConfig()
        self._latencies: deque = deque(maxlen=self.config.latency_window_size)
        self._predictions: deque = deque(maxlen=self.config.drift_window_size)
        self._request_times: deque = deque(maxlen=10000)
        self._error_count: int = 0
        self._total_count: int = 0
        self._start_time: float = time.time()
        self._alert_callbacks: List[Callable] = []
        self._per_model_stats: Dict[str, Dict[str, Any]] = {}

    def record_latency(self, latency_ms: float) -> None:
        """Record a prediction latency in milliseconds."""
        self._latencies.append(latency_ms)

    def record_prediction(self, prediction: float, model_name: str = "") -> None:
        """Record a prediction value for drift monitoring."""
        self._predictions.append(prediction)
        self._request_times.append(time.time())
        self._total_count += 1

        if model_name:
            if model_name not in self._per_model_stats:
                self._per_model_stats[model_name] = {"count": 0, "predictions": []}
            self._per_model_stats[model_name]["count"] += 1
            self._per_model_stats[model_name]["predictions"].append(prediction)
            # Keep only recent predictions per model
            if len(self._per_model_stats[model_name]["predictions"]) > 1000:
                self._per_model_stats[model_name]["predictions"] = \
                    self._per_model_stats[model_name]["predictions"][-500:]

    def record_error(self, error_type: str = "unknown") -> None:
        """Record an inference error."""
        self._error_count += 1
        self._total_count += 1

    def record_cache_hit(self, hit: bool) -> None:
        """Track cache hit/miss (used by PredictionCache integration)."""
        if not hasattr(self, '_cache_hits'):
            self._cache_hits = 0
            self._cache_misses = 0
        if hit:
            self._cache_hits += 1
        else:
            self._cache_misses += 1

    def get_latency_stats(self) -> LatencyMetric:
        """Get current latency statistics."""
        if not self._latencies:
            return LatencyMetric()

        sorted_lat = sorted(self._latencies)
        n = len(sorted_lat)
        return LatencyMetric(
            avg_ms=sum(sorted_lat) / n,
            p50_ms=sorted_lat[int(n * 0.5)] if n > 0 else 0.0,
            p95_ms=sorted_lat[int(n * 0.95)] if n > 1 else sorted_lat[0],
            p99_ms=sorted_lat[int(n * 0.99)] if n > 1 else sorted_lat[0],
            max_ms=max(sorted_lat),
            min_ms=min(sorted_lat),
            count=n,
        )

    def get_qps_stats(self) -> QPSMetric:
        """Get current QPS statistics."""
        now = time.time()
        window = self.config.qps_window_seconds
        recent = [t for t in self._request_times if now - t <= window]

        elapsed = now - self._start_time
        avg_qps = self._total_count / elapsed if elapsed > 0 else 0.0

        return QPSMetric(
            current_qps=len(recent) / window if window > 0 else 0.0,
            peak_qps=max(getattr(self, '_peak_qps', 0.0), avg_qps),
            avg_qps=round(avg_qps, 1),
            total_requests=self._total_count,
            window_seconds=window,
        )

    def get_drift_stats(self, historical_mean: float = 0.5, historical_std: float = 0.2) -> DriftMetric:
        """Get prediction drift statistics.

        Args:
            historical_mean: Baseline mean prediction.
            historical_std: Baseline prediction std dev.

        Returns:
            DriftMetric with current vs historical comparison.
        """
        if not self._predictions:
            return DriftMetric(
                historical_mean=historical_mean,
                historical_std=historical_std,
            )

        import math
        preds = list(self._predictions)
        n = len(preds)
        current_mean = sum(preds) / n
        current_std = math.sqrt(sum((p - current_mean) ** 2 for p in preds) / n) if n > 1 else 0.0

        # PSI (Population Stability Index) approximation
        psi = self._compute_psi(current_mean, current_std, historical_mean, historical_std)

        return DriftMetric(
            prediction_mean=current_mean,
            prediction_std=current_std,
            historical_mean=historical_mean,
            historical_std=historical_std,
            psi=round(psi, 4),
            drift_detected=psi > self.config.drift_threshold_psi,
        )

    def get_error_rate(self) -> float:
        """Get current error rate."""
        if self._total_count == 0:
            return 0.0
        return self._error_count / self._total_count

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache hit/miss statistics."""
        hits = getattr(self, '_cache_hits', 0)
        misses = getattr(self, '_cache_misses', 0)
        total = hits + misses
        return {
            "hits": hits,
            "misses": misses,
            "hit_rate": round(hits / total, 4) if total > 0 else 0.0,
        }

    def get_per_model_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get per-model statistics."""
        result = {}
        for name, stats in self._per_model_stats.items():
            preds = stats.get("predictions", [])
            result[name] = {
                "count": stats["count"],
                "prediction_mean": round(sum(preds) / len(preds), 4) if preds else 0.0,
            }
        return result

    def check_health(self) -> HealthStatus:
        """Health check based on configured thresholds.

        Returns:
            HealthStatus: HEALTHY, DEGRADED, or UNHEALTHY.
        """
        issues = 0

        # Check error rate
        if self.get_error_rate() > self.config.error_rate_threshold:
            issues += 2

        # Check latency
        latency = self.get_latency_stats()
        if latency.p99_ms > self.config.latency_p99_threshold_ms:
            issues += 1

        # Check drift
        drift = self.get_drift_stats()
        if drift.drift_detected:
            issues += 1

        if issues >= 3:
            return HealthStatus.UNHEALTHY
        if issues >= 1:
            return HealthStatus.DEGRADED
        return HealthStatus.HEALTHY

    def get_stats(self) -> Dict[str, Any]:
        """Get comprehensive monitoring statistics."""
        health = self.check_health()
        latency = self.get_latency_stats()
        qps = self.get_qps_stats()
        drift = self.get_drift_stats()
        return {
            "health": health.value,
            "uptime_seconds": round(time.time() - self._start_time, 1),
            "latency": latency.to_dict(),
            "qps": qps.to_dict(),
            "drift": drift.to_dict(),
            "error_rate": round(self.get_error_rate(), 4),
            "total_requests": self._total_count,
            "error_count": self._error_count,
            "cache": self.get_cache_stats(),
            "per_model": self.get_per_model_stats(),
        }

    def add_alert_callback(self, callback: Callable[[str, Dict[str, Any]], None]) -> None:
        """Register an alert callback.

        Args:
            callback: Function(alert_type, stats_dict).
        """
        self._alert_callbacks.append(callback)

    def reset(self) -> None:
        """Reset all metrics."""
        self._latencies.clear()
        self._predictions.clear()
        self._request_times.clear()
        self._error_count = 0
        self._total_count = 0
        self._start_time = time.time()
        self._per_model_stats.clear()
        self._cache_hits = 0
        self._cache_misses = 0
        self._peak_qps = 0.0

    # ---- internal ----

    @staticmethod
    def _compute_psi(current_mean: float, current_std: float, hist_mean: float, hist_std: float) -> float:
        """Approximate PSI using normal distribution assumption."""
        import math
        if hist_std == 0:
            return 0.0 if abs(current_mean - hist_mean) < 1e-6 else 1.0
        # Normalized distance
        z = abs(current_mean - hist_mean) / hist_std
        # Simple PSI approximation: bounded by [0, 1]
        return min(1.0, z / 6.0)
