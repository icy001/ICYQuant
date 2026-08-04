"""
Rotation metrics collection.

Provides Prometheus-compatible metrics
for rotation operations, including
success/failure rates, duration tracking,
and dual-key transition statistics.
"""

from __future__ import annotations

import logging
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

try:
    from prometheus_client import Counter, Gauge, Histogram, generate_latest
    _HAS_PROMETHEUS = True
except ImportError:
    _HAS_PROMETHEUS = False


class RotationMetrics:
    """
    Rotation metrics collector.

    Tracks rotation operations with
    Prometheus-compatible metrics and
    in-memory fallbacks when Prometheus
    is not available.

    Metrics:
    - icyquant_secret_rotation_total
    - icyquant_secret_rotation_success_total
    - icyquant_secret_rotation_failure_total
    - icyquant_secret_rotation_duration_seconds
    - icyquant_secret_expiration_total
    - icyquant_secret_dualkey_transition_total
    """

    METRICS_PREFIX = "icyquant_secret_rotation_"

    def __init__(self, enabled: bool = True) -> None:
        """
        Initialize rotation metrics.

        Args:
            enabled: Whether metrics collection is enabled.
        """
        self._enabled = enabled
        self._lock = threading.Lock()

        # In-memory counters
        self._counters: Dict[str, Dict[str, float]] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._gauges: Dict[str, float] = {}

        # Prometheus metrics
        self._prom_counters: Dict[str, Any] = {}
        self._prom_histograms: Dict[str, Any] = {}
        self._prom_gauges: Dict[str, Any] = {}

        if enabled and _HAS_PROMETHEUS:
            self._init_prometheus()

    def _init_prometheus(self) -> None:
        """Initialize Prometheus metrics."""
        try:
            self._prom_counters["rotation_total"] = Counter(
                f"{self.METRICS_PREFIX}total",
                "Total rotation operations",
                ["secret_type", "strategy"],
            )
            self._prom_counters["rotation_success"] = Counter(
                f"{self.METRICS_PREFIX}success_total",
                "Total successful rotations",
                ["secret_type"],
            )
            self._prom_counters["rotation_failure"] = Counter(
                f"{self.METRICS_PREFIX}failure_total",
                "Total failed rotations",
                ["secret_type", "reason"],
            )
            self._prom_counters["expiration_total"] = Counter(
                f"{self.METRICS_PREFIX}expiration_total",
                "Total secret expirations",
                ["level"],
            )
            self._prom_counters["dualkey_total"] = Counter(
                f"{self.METRICS_PREFIX}dualkey_transition_total",
                "Total dual-key transitions",
                ["phase"],
            )

            self._prom_histograms["rotation_duration"] = Histogram(
                f"{self.METRICS_PREFIX}duration_seconds",
                "Rotation operation duration",
                ["secret_type"],
            )

            self._prom_gauges["active_rotations"] = Gauge(
                f"{self.METRICS_PREFIX}active_rotations",
                "Number of active rotation operations",
            )
            self._prom_gauges["pending_approvals"] = Gauge(
                f"{self.METRICS_PREFIX}pending_approvals",
                "Number of pending approval requests",
            )
            self._prom_gauges["overdue_secrets"] = Gauge(
                f"{self.METRICS_PREFIX}overdue_secrets",
                "Number of overdue secrets",
            )
        except Exception:
            self._prom_counters.clear()
            self._prom_histograms.clear()
            self._prom_gauges.clear()

    def record_rotation(
        self,
        secret_type: str = "unknown",
        strategy: str = "scheduled",
        success: bool = True,
        duration: float = 0.0,
        failure_reason: str = "",
    ) -> None:
        """
        Record a rotation operation.

        Args:
            secret_type: Type of secret rotated.
            strategy: Rotation strategy used.
            success: Whether rotation succeeded.
            duration: Rotation duration in seconds.
            failure_reason: Failure reason if failed.
        """
        if not self._enabled:
            return

        with self._lock:
            # Total counter
            key = "rotation_total"
            self._counters.setdefault(key, {})
            label = f"{secret_type}/{strategy}"
            self._counters[key][label] = self._counters[key].get(label, 0) + 1

            # Success/failure
            if success:
                skey = "rotation_success"
                self._counters.setdefault(skey, {})
                self._counters[skey][secret_type] = (
                    self._counters[skey].get(secret_type, 0) + 1
                )
            else:
                fkey = "rotation_failure"
                self._counters.setdefault(fkey, {})
                label = f"{secret_type}/{failure_reason}"
                self._counters[fkey][label] = (
                    self._counters[fkey].get(label, 0) + 1
                )

            # Duration histogram
            if duration > 0:
                dkey = f"rotation_duration_{secret_type}"
                if dkey not in self._histograms:
                    self._histograms[dkey] = []
                self._histograms[dkey].append(duration)

        # Prometheus
        if _HAS_PROMETHEUS:
            if "rotation_total" in self._prom_counters:
                self._prom_counters["rotation_total"].labels(
                    secret_type=secret_type, strategy=strategy
                ).inc()
            if success and "rotation_success" in self._prom_counters:
                self._prom_counters["rotation_success"].labels(
                    secret_type=secret_type
                ).inc()
            if not success and "rotation_failure" in self._prom_counters:
                self._prom_counters["rotation_failure"].labels(
                    secret_type=secret_type, reason=failure_reason
                ).inc()
            if duration > 0 and "rotation_duration" in self._prom_histograms:
                self._prom_histograms["rotation_duration"].labels(
                    secret_type=secret_type
                ).observe(duration)

    def record_expiration(
        self,
        level: str = "warning",
    ) -> None:
        """
        Record a secret expiration event.

        Args:
            level: Expiration warning level.
        """
        if not self._enabled:
            return

        with self._lock:
            key = "expiration_total"
            self._counters.setdefault(key, {})
            self._counters[key][level] = (
                self._counters[key].get(level, 0) + 1
            )

        if _HAS_PROMETHEUS and "expiration_total" in self._prom_counters:
            self._prom_counters["expiration_total"].labels(level=level).inc()

    def record_dualkey_transition(
        self,
        phase: str = "initiated",
    ) -> None:
        """
        Record a dual-key transition phase.

        Args:
            phase: Transition phase name.
        """
        if not self._enabled:
            return

        with self._lock:
            key = "dualkey_total"
            self._counters.setdefault(key, {})
            self._counters[key][phase] = (
                self._counters[key].get(phase, 0) + 1
            )

        if _HAS_PROMETHEUS and "dualkey_total" in self._prom_counters:
            self._prom_counters["dualkey_total"].labels(phase=phase).inc()

    def set_active_rotations(
        self,
        count: int,
    ) -> None:
        """Set active rotation count."""
        self._gauges["active_rotations"] = count
        if _HAS_PROMETHEUS and "active_rotations" in self._prom_gauges:
            self._prom_gauges["active_rotations"].set(count)

    def set_pending_approvals(
        self,
        count: int,
    ) -> None:
        """Set pending approval count."""
        self._gauges["pending_approvals"] = count
        if _HAS_PROMETHEUS and "pending_approvals" in self._prom_gauges:
            self._prom_gauges["pending_approvals"].set(count)

    def set_overdue_secrets(
        self,
        count: int,
    ) -> None:
        """Set overdue secrets count."""
        self._gauges["overdue_secrets"] = count
        if _HAS_PROMETHEUS and "overdue_secrets" in self._prom_gauges:
            self._prom_gauges["overdue_secrets"].set(count)

    def generate_prometheus(self) -> str:
        """
        Generate Prometheus text format metrics.

        Returns:
            Prometheus text format string.
        """
        if _HAS_PROMETHEUS:
            try:
                result = generate_latest()
                if isinstance(result, bytes):
                    result = result.decode("utf-8")
                return result
            except Exception:
                pass

        lines: List[str] = []
        for name, labels in self._counters.items():
            total = sum(labels.values())
            lines.append(f"# HELP {self.METRICS_PREFIX}{name} Total {name}")
            lines.append(f"# TYPE {self.METRICS_PREFIX}{name} counter")
            for label, value in labels.items():
                parts = label.split("/", 1) if "/" in label else (label, "")
                lines.append(
                    f'{self.METRICS_PREFIX}{name}{{label="{label}"}} {value}'
                )

        for name, value in self._gauges.items():
            lines.append(f"# HELP {self.METRICS_PREFIX}{name} Gauge")
            lines.append(f"# TYPE {self.METRICS_PREFIX}{name} gauge")
            lines.append(f"{self.METRICS_PREFIX}{name} {value}")

        return "\n".join(lines) + "\n"

    def get_stats(self) -> Dict[str, Any]:
        """Get metrics statistics."""
        with self._lock:
            return {
                "enabled": self._enabled,
                "counters": {
                    k: sum(v.values()) for k, v in self._counters.items()
                },
                "gauges": dict(self._gauges),
                "histograms": {
                    k: {
                        "count": len(v),
                        "avg": sum(v) / len(v) if v else 0,
                    }
                    for k, v in self._histograms.items()
                },
                "has_prometheus": _HAS_PROMETHEUS,
            }
