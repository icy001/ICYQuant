"""
Feature flag platform runtime monitoring.

Provides Prometheus-compatible metrics for
the feature flag platform runtime including:
    - Snapshot version tracking
    - Reload counts
    - Evaluation latency
    - Canary active status
    - Experiment running status
    - Runtime sync counts
"""

from __future__ import annotations

import logging
import time
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class FeatureFlagRuntimeMetrics:
    """
    Collects Prometheus-compatible metrics for the
    feature flag platform runtime.

    Metrics follow the 'icyquant_' prefix convention
    and use standard labels for aggregation.

    Metrics collected:
        - icyquant_feature_snapshot_version (gauge)
        - icyquant_feature_reload_total (counter)
        - icyquant_feature_evaluation_latency_seconds (histogram)
        - icyquant_feature_canary_active (gauge)
        - icyquant_feature_experiment_running (gauge)
        - icyquant_feature_runtime_sync_total (counter)
        - icyquant_feature_evaluation_total (counter)
        - icyquant_feature_evaluation_errors_total (counter)

    Usage:
        metrics = FeatureFlagRuntimeMetrics()
        metrics.record_snapshot_version(42)
        metrics.record_evaluation(latency_ms=5.0)
        snap = metrics.snapshot()
    """

    def __init__(self) -> None:
        self._snapshot_version: float = 0.0
        self._reload_total: float = 0.0
        self._evaluation_total: float = 0.0
        self._evaluation_errors_total: float = 0.0
        self._runtime_sync_total: float = 0.0
        self._canary_active: float = 0.0
        self._experiment_running: float = 0.0

        # Latency tracking (buckets in milliseconds)
        self._latency_sum_ms: float = 0.0
        self._latency_count: float = 0.0
        self._latency_buckets: Dict[str, float] = {
            "0_1ms": 0.0,
            "1_5ms": 0.0,
            "5_10ms": 0.0,
            "10_50ms": 0.0,
            "50_100ms": 0.0,
            "100_500ms": 0.0,
            "500ms_plus": 0.0,
        }

    def record_snapshot_version(self, version: int) -> None:
        """Record current snapshot version."""
        self._snapshot_version = float(version)

    def record_reload(self) -> None:
        """Record a reload event."""
        self._reload_total += 1

    def record_evaluation(
        self,
        latency_ms: float = 0.0,
        success: bool = True,
    ) -> None:
        """
        Record an evaluation.

        Args:
            latency_ms: Evaluation latency in milliseconds.
            success: Whether the evaluation succeeded.
        """
        self._evaluation_total += 1

        if not success:
            self._evaluation_errors_total += 1

        # Track latency
        self._latency_sum_ms += latency_ms
        self._latency_count += 1

        # Bucket latency
        if latency_ms <= 1:
            self._latency_buckets["0_1ms"] += 1
        elif latency_ms <= 5:
            self._latency_buckets["1_5ms"] += 1
        elif latency_ms <= 10:
            self._latency_buckets["5_10ms"] += 1
        elif latency_ms <= 50:
            self._latency_buckets["10_50ms"] += 1
        elif latency_ms <= 100:
            self._latency_buckets["50_100ms"] += 1
        elif latency_ms <= 500:
            self._latency_buckets["100_500ms"] += 1
        else:
            self._latency_buckets["500ms_plus"] += 1

    def record_runtime_sync(self) -> None:
        """Record a runtime synchronization event."""
        self._runtime_sync_total += 1

    def set_canary_active(self, active: int) -> None:
        """Set number of active canary deployments."""
        self._canary_active = float(active)

    def set_experiment_running(self, running: int) -> None:
        """Set number of running experiments."""
        self._experiment_running = float(running)

    def snapshot(self) -> Dict[str, Any]:
        """
        Get current metrics snapshot.

        Returns:
            Dictionary of all metric values.
        """
        avg_latency = (
            self._latency_sum_ms / self._latency_count
            if self._latency_count > 0
            else 0.0
        )
        error_rate = (
            self._evaluation_errors_total / self._evaluation_total
            if self._evaluation_total > 0
            else 0.0
        )

        return {
            # Gauges
            "icyquant_feature_snapshot_version": self._snapshot_version,
            "icyquant_feature_canary_active": self._canary_active,
            "icyquant_feature_experiment_running": self._experiment_running,
            # Counters
            "icyquant_feature_reload_total": self._reload_total,
            "icyquant_feature_evaluation_total": self._evaluation_total,
            "icyquant_feature_evaluation_errors_total": self._evaluation_errors_total,
            "icyquant_feature_runtime_sync_total": self._runtime_sync_total,
            # Derived
            "icyquant_feature_evaluation_avg_latency_ms": avg_latency,
            "icyquant_feature_evaluation_error_rate": error_rate,
            # Latency histogram buckets
            "latency_buckets": dict(self._latency_buckets),
        }

    def get_counter_values(self) -> Dict[str, float]:
        """Get counter metric values for Prometheus export."""
        return {
            "icyquant_feature_reload_total": self._reload_total,
            "icyquant_feature_evaluation_total": self._evaluation_total,
            "icyquant_feature_evaluation_errors_total": self._evaluation_errors_total,
            "icyquant_feature_runtime_sync_total": self._runtime_sync_total,
        }

    def get_gauge_values(self) -> Dict[str, float]:
        """Get gauge metric values for Prometheus export."""
        return {
            "icyquant_feature_snapshot_version": self._snapshot_version,
            "icyquant_feature_canary_active": self._canary_active,
            "icyquant_feature_experiment_running": self._experiment_running,
        }

    def reset(self) -> None:
        """Reset all metrics."""
        self._snapshot_version = 0.0
        self._reload_total = 0.0
        self._evaluation_total = 0.0
        self._evaluation_errors_total = 0.0
        self._runtime_sync_total = 0.0
        self._canary_active = 0.0
        self._experiment_running = 0.0
        self._latency_sum_ms = 0.0
        self._latency_count = 0.0
        for key in self._latency_buckets:
            self._latency_buckets[key] = 0.0
