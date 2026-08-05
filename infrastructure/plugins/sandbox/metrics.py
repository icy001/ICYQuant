"""Sandbox-specific metrics collection.

Provides :class:`SandboxMetrics` for recording and reporting
sandbox operational metrics including sandbox lifecycle events,
policy checks, violations, and resource usage, with thread-safe
counter, gauge, and histogram support.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

_METRIC_TOTAL = "icyquant_sandbox_total"
_METRIC_VIOLATIONS = "icyquant_sandbox_violations_total"
_METRIC_ACCESS_DENIED = "icyquant_sandbox_access_denied_total"
_METRIC_RESOURCE_EXCEEDED = (
    "icyquant_sandbox_resource_exceeded_total"
)
_METRIC_POLICY_CHECK = "icyquant_sandbox_policy_check_total"
_METRIC_AUDIT_EVENT = "icyquant_sandbox_audit_events_total"
_METRIC_SANDBOX_START = "icyquant_sandbox_start_total"
_METRIC_SANDBOX_STOP = "icyquant_sandbox_stop_total"


class SandboxMetrics:
    """Collects and reports sandbox-specific operational metrics.

    Provides counters, gauges, and histograms for tracking
    sandbox lifecycle events, policy decisions, violations,
    and resource usage across all plugins.

    All operations are thread-safe via an ``RLock``.

    Attributes:
        _counters: Map of metric name → counter value.
        _gauges: Map of metric name → gauge value.
        _histograms: Map of metric name → list of samples.
        _plugin_metrics: Map of plugin_id → per-plugin metrics.
        _lock: Thread-safe reentrant lock.
    """

    def __init__(self) -> None:
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._histograms: Dict[str, List[float]] = {}
        self._plugin_metrics: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.RLock()
        self._max_histogram_samples = 1000
        self._init_defaults()

    def _init_defaults(self) -> None:
        """Initialize default metric counters."""
        defaults = [
            _METRIC_TOTAL,
            _METRIC_VIOLATIONS,
            _METRIC_ACCESS_DENIED,
            _METRIC_RESOURCE_EXCEEDED,
            _METRIC_POLICY_CHECK,
            _METRIC_AUDIT_EVENT,
            _METRIC_SANDBOX_START,
            _METRIC_SANDBOX_STOP,
        ]
        for name in defaults:
            self._counters[name] = 0.0

    def record_sandbox_start(
        self, plugin_id: str, duration_ms: float
    ) -> None:
        """Record a sandbox start event.

        Args:
            plugin_id: Unique identifier for the plugin.
            duration_ms: Start operation duration in milliseconds.
        """
        with self._lock:
            self._counters[_METRIC_SANDBOX_START] = (
                self._counters.get(_METRIC_SANDBOX_START, 0) + 1
            )
            self._counters[_METRIC_TOTAL] = (
                self._counters.get(_METRIC_TOTAL, 0) + 1
            )
            self._record_plugin_event(
                plugin_id,
                "sandbox_start",
                duration_ms,
            )
            self._record_histogram(
                "icyquant_sandbox_start_duration_ms",
                duration_ms,
            )

    def record_sandbox_stop(
        self, plugin_id: str, duration_ms: float
    ) -> None:
        """Record a sandbox stop event.

        Args:
            plugin_id: Unique identifier for the plugin.
            duration_ms: Stop operation duration in milliseconds.
        """
        with self._lock:
            self._counters[_METRIC_SANDBOX_STOP] = (
                self._counters.get(_METRIC_SANDBOX_STOP, 0) + 1
            )
            self._record_plugin_event(
                plugin_id,
                "sandbox_stop",
                duration_ms,
            )
            self._record_histogram(
                "icyquant_sandbox_stop_duration_ms",
                duration_ms,
            )

    def record_violation(
        self, plugin_id: str, violation_type: str
    ) -> None:
        """Record a sandbox policy violation.

        Args:
            plugin_id: Unique identifier for the plugin.
            violation_type: The type of violation (e.g.
                ``"memory_limit"``, ``"network_access"``).
        """
        with self._lock:
            self._counters[_METRIC_VIOLATIONS] = (
                self._counters.get(_METRIC_VIOLATIONS, 0) + 1
            )
            violation_key = (
                f"icyquant_sandbox_violations_{violation_type}_total"
            )
            self._counters[violation_key] = (
                self._counters.get(violation_key, 0) + 1
            )
            self._record_plugin_event(
                plugin_id,
                "violation",
                0,
                {"violation_type": violation_type},
            )

    def record_access_denied(
        self, plugin_id: str, resource: str
    ) -> None:
        """Record an access denial event.

        Args:
            plugin_id: Unique identifier for the plugin.
            resource: The resource that was denied access.
        """
        with self._lock:
            self._counters[_METRIC_ACCESS_DENIED] = (
                self._counters.get(_METRIC_ACCESS_DENIED, 0) + 1
            )
            resource_key = (
                f"icyquant_sandbox_access_denied_{resource}_total"
            )
            self._counters[resource_key] = (
                self._counters.get(resource_key, 0) + 1
            )
            self._record_plugin_event(
                plugin_id,
                "access_denied",
                0,
                {"resource": resource},
            )

    def record_resource_exceeded(
        self,
        plugin_id: str,
        resource: str,
        limit: float,
        actual: float,
    ) -> None:
        """Record a resource limit exceeded event.

        Args:
            plugin_id: Unique identifier for the plugin.
            resource: The resource type that was exceeded.
            limit: The configured limit.
            actual: The actual usage that exceeded the limit.
        """
        with self._lock:
            self._counters[_METRIC_RESOURCE_EXCEEDED] = (
                self._counters.get(
                    _METRIC_RESOURCE_EXCEEDED, 0
                )
                + 1
            )
            resource_key = (
                f"icyquant_sandbox_resource_exceeded_{resource}_total"
            )
            self._counters[resource_key] = (
                self._counters.get(resource_key, 0) + 1
            )
            self._record_plugin_event(
                plugin_id,
                "resource_exceeded",
                0,
                {
                    "resource": resource,
                    "limit": limit,
                    "actual": actual,
                },
            )

    def record_policy_check(
        self,
        plugin_id: str,
        action: str,
        allowed: bool,
    ) -> None:
        """Record a policy check event.

        Args:
            plugin_id: Unique identifier for the plugin.
            action: The action that was checked.
            allowed: Whether the action was allowed.
        """
        with self._lock:
            self._counters[_METRIC_POLICY_CHECK] = (
                self._counters.get(_METRIC_POLICY_CHECK, 0) + 1
            )
            outcome = "allowed" if allowed else "denied"
            outcome_key = (
                f"icyquant_sandbox_policy_check_{outcome}_total"
            )
            self._counters[outcome_key] = (
                self._counters.get(outcome_key, 0) + 1
            )
            action_key = (
                f"icyquant_sandbox_policy_check_{action}_total"
            )
            self._counters[action_key] = (
                self._counters.get(action_key, 0) + 1
            )
            self._record_plugin_event(
                plugin_id,
                "policy_check",
                0,
                {"action": action, "allowed": allowed},
            )

    def record_audit_event(
        self, plugin_id: str, event_type: str
    ) -> None:
        """Record an audit event.

        Args:
            plugin_id: Unique identifier for the plugin.
            event_type: The type of audit event.
        """
        with self._lock:
            self._counters[_METRIC_AUDIT_EVENT] = (
                self._counters.get(_METRIC_AUDIT_EVENT, 0) + 1
            )
            type_key = (
                f"icyquant_sandbox_audit_{event_type}_total"
            )
            self._counters[type_key] = (
                self._counters.get(type_key, 0) + 1
            )
            self._record_plugin_event(
                plugin_id,
                "audit_event",
                0,
                {"event_type": event_type},
            )

    def increment_counter(
        self, name: str, value: float = 1.0
    ) -> None:
        """Increment an arbitrary counter metric.

        Args:
            name: The metric name.
            value: The amount to increment by.
        """
        with self._lock:
            self._counters[name] = (
                self._counters.get(name, 0.0) + value
            )

    def set_gauge(self, name: str, value: float) -> None:
        """Set a gauge metric to a specific value.

        Args:
            name: The metric name.
            value: The gauge value.
        """
        with self._lock:
            self._gauges[name] = value

    def get_counter(self, name: str) -> int:
        """Get the current value of a counter.

        Args:
            name: The metric name.

        Returns:
            The counter value as an integer.
        """
        with self._lock:
            return int(self._counters.get(name, 0))

    def get_gauge(self, name: str) -> float:
        """Get the current value of a gauge.

        Args:
            name: The metric name.

        Returns:
            The gauge value as a float.
        """
        with self._lock:
            return self._gauges.get(name, 0.0)

    def snapshot(self) -> Dict[str, Any]:
        """Get a full metrics snapshot.

        Returns:
            A dictionary with all counters, gauges,
            histograms, and per-plugin metrics.
        """
        with self._lock:
            histograms = {}
            for name, samples in self._histograms.items():
                if not samples:
                    continue
                sorted_samples = sorted(samples)
                count = len(sorted_samples)
                histograms[name] = {
                    "count": count,
                    "min": sorted_samples[0],
                    "max": sorted_samples[-1],
                    "avg": sum(sorted_samples) / count,
                    "p50": sorted_samples[
                        min(int(count * 0.50), count - 1)
                    ],
                    "p95": sorted_samples[
                        min(int(count * 0.95), count - 1)
                    ],
                    "p99": sorted_samples[
                        min(int(count * 0.99), count - 1)
                    ],
                }

            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "histograms": histograms,
                "plugins": {
                    pid: dict(metrics)
                    for pid, metrics in self._plugin_metrics.items()
                },
                "timestamp": time.time(),
            }

    def reset(self) -> None:
        """Reset all metrics to their initial state."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._plugin_metrics.clear()
            self._init_defaults()
            logger.info("Sandbox metrics reset")

    def _record_plugin_event(
        self,
        plugin_id: str,
        event_type: str,
        duration_ms: float,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a per-plugin event (must be called with lock).

        Args:
            plugin_id: The plugin involved.
            event_type: The type of event.
            duration_ms: Duration in milliseconds.
            details: Optional event details.
        """
        if plugin_id not in self._plugin_metrics:
            self._plugin_metrics[plugin_id] = {
                "events": 0,
                "violations": 0,
                "access_denied": 0,
                "policy_checks": 0,
                "last_event": None,
            }

        pm = self._plugin_metrics[plugin_id]
        pm["events"] += 1
        pm["last_event"] = {
            "type": event_type,
            "duration_ms": duration_ms,
            "details": details or {},
            "timestamp": time.time(),
        }

        if event_type == "violation":
            pm["violations"] += 1
        elif event_type == "access_denied":
            pm["access_denied"] += 1
        elif event_type == "policy_check":
            pm["policy_checks"] += 1

    def _record_histogram(
        self, name: str, value: float
    ) -> None:
        """Record a histogram sample (must be called with lock).

        Args:
            name: The histogram metric name.
            value: The sample value.
        """
        if name not in self._histograms:
            self._histograms[name] = []
        samples = self._histograms[name]
        samples.append(value)
        if len(samples) > self._max_histogram_samples:
            self._histograms[name] = samples[
                -self._max_histogram_samples:
            ]

    def get_stats(self) -> Dict[str, Any]:
        """Get metrics statistics summary.

        Returns:
            A dictionary with counter values, gauge values,
            histogram summaries, and per-plugin summaries.
        """
        with self._lock:
            total_plugins = len(self._plugin_metrics)
            total_violations = sum(
                pm.get("violations", 0)
                for pm in self._plugin_metrics.values()
            )
            total_access_denied = sum(
                pm.get("access_denied", 0)
                for pm in self._plugin_metrics.values()
            )
            return {
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "total_plugins_tracked": total_plugins,
                "total_violations": total_violations,
                "total_access_denied": total_access_denied,
                "histogram_count": len(self._histograms),
            }