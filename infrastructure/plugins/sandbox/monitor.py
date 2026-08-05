"""Sandbox monitoring and metrics collection.

Provides :class:`SandboxMonitor` for runtime monitoring of
sandboxed plugins and :class:`SandboxMetrics` for collecting
and reporting operational metrics.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class SandboxMetrics:
    """Collects and reports sandbox operational metrics.

    Tracks counters, gauges, and timing data for sandbox
    operations such as creation, destruction, and violations.

    Attributes:
        _counters: Map of metric name → counter value.
        _gauges: Map of metric name → gauge value.
        _timings: Map of metric name → list of timing samples.
        _lock: Thread-safe reentrant lock.
    """

    def __init__(self) -> None:
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._timings: Dict[str, List[float]] = {}
        self._lock = threading.RLock()
        self._max_timing_samples = 1000

    def increment_counter(
        self, name: str, value: float = 1.0
    ) -> None:
        """Increment a counter metric.

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

    def record_timing(self, name: str, duration: float) -> None:
        """Record a timing sample for a metric.

        Args:
            name: The metric name.
            duration: The duration in seconds.
        """
        with self._lock:
            if name not in self._timings:
                self._timings[name] = []
            samples = self._timings[name]
            samples.append(duration)
            if len(samples) > self._max_timing_samples:
                self._timings[name] = samples[-self._max_timing_samples:]

    def get_counters(self) -> Dict[str, float]:
        """Get all counter values.

        Returns:
            A dictionary of counter name → value.
        """
        with self._lock:
            return dict(self._counters)

    def get_gauges(self) -> Dict[str, float]:
        """Get all gauge values.

        Returns:
            A dictionary of gauge name → value.
        """
        with self._lock:
            return dict(self._gauges)

    def get_timings(self) -> Dict[str, Dict[str, float]]:
        """Get timing statistics for all timing metrics.

        Returns:
            A dictionary of metric name → statistics dict with
            ``count``, ``min``, ``max``, ``avg``, ``p50``, ``p95``,
            and ``p99``.
        """
        with self._lock:
            result: Dict[str, Dict[str, float]] = {}
            for name, samples in self._timings.items():
                if not samples:
                    continue
                sorted_samples = sorted(samples)
                count = len(sorted_samples)
                result[name] = {
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
            return result

    def reset(self) -> None:
        """Reset all metrics to their initial state."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._timings.clear()

    def get_stats(self) -> Dict[str, Any]:
        """Get a summary of all metrics.

        Returns:
            A dictionary with counters, gauges, and timing summaries.
        """
        return {
            "counters": self.get_counters(),
            "gauges": self.get_gauges(),
            "timings": self.get_timings(),
        }


class SandboxMonitor:
    """Monitors sandbox health and triggers alerts on violations.

    Periodically checks resource usage, detects policy violations,
    and invokes registered alert handlers.

    Attributes:
        _plugins: Map of plugin_id → monitored plugin info.
        _alert_handlers: List of alert handler callables.
        _metrics: SandboxMetrics instance for recording events.
        _lock: Thread-safe reentrant lock.
    """

    def __init__(self, metrics: Optional[SandboxMetrics] = None) -> None:
        """Initialize the sandbox monitor.

        Args:
            metrics: Optional shared SandboxMetrics instance.
                A new one is created if not provided.
        """
        self._plugins: Dict[str, Dict[str, Any]] = {}
        self._alert_handlers: List[
            Callable[[str, str, Dict[str, Any]], None]
        ] = []
        self._metrics = metrics or SandboxMetrics()
        self._lock = threading.RLock()
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None

    def register_plugin(
        self,
        plugin_id: str,
        status: str = "unknown",
    ) -> None:
        """Register a plugin for monitoring.

        Args:
            plugin_id: Unique identifier for the plugin.
            status: Initial status string.
        """
        with self._lock:
            self._plugins[plugin_id] = {
                "plugin_id": plugin_id,
                "status": status,
                "registered_at": time.time(),
                "last_check": time.time(),
                "violations": 0,
            }
            self._metrics.increment_counter("plugins_registered")
            self._metrics.set_gauge(
                "active_plugins", len(self._plugins)
            )

    def unregister_plugin(self, plugin_id: str) -> None:
        """Remove a plugin from monitoring.

        Args:
            plugin_id: Unique identifier for the plugin.
        """
        with self._lock:
            self._plugins.pop(plugin_id, None)
            self._metrics.increment_counter("plugins_unregistered")
            self._metrics.set_gauge(
                "active_plugins", len(self._plugins)
            )

    def update_status(
        self, plugin_id: str, status: str
    ) -> None:
        """Update the status of a monitored plugin.

        Args:
            plugin_id: Unique identifier for the plugin.
            status: New status string.
        """
        with self._lock:
            if plugin_id in self._plugins:
                self._plugins[plugin_id]["status"] = status
                self._plugins[plugin_id]["last_check"] = time.time()

    def record_violation(
        self,
        plugin_id: str,
        violation_type: str,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Record a sandbox policy violation.

        Args:
            plugin_id: The plugin that committed the violation.
            violation_type: The type of violation (e.g.
                ``"memory_limit"``, ``"network_access"``).
            details: Optional additional details.
        """
        with self._lock:
            if plugin_id in self._plugins:
                self._plugins[plugin_id]["violations"] += 1
                self._plugins[plugin_id]["last_check"] = time.time()

        self._metrics.increment_counter("violations")
        self._metrics.increment_counter(
            f"violations_{violation_type}"
        )

        alert = {
            "plugin_id": plugin_id,
            "violation_type": violation_type,
            "details": details or {},
            "timestamp": time.time(),
        }
        self._fire_alerts("violation", plugin_id, alert)
        logger.warning(
            "Sandbox violation: plugin=%s type=%s",
            plugin_id, violation_type,
        )

    def add_alert_handler(
        self,
        handler: Callable[[str, str, Dict[str, Any]], None],
    ) -> None:
        """Register an alert handler.

        Args:
            handler: A callable receiving (alert_type, plugin_id, data).
        """
        self._alert_handlers.append(handler)

    def _fire_alerts(
        self, alert_type: str, plugin_id: str, data: Dict[str, Any]
    ) -> None:
        """Fire all registered alert handlers.

        Args:
            alert_type: The type of alert.
            plugin_id: The plugin involved.
            data: The alert data.
        """
        for handler in self._alert_handlers:
            try:
                handler(alert_type, plugin_id, data)
            except Exception:
                logger.exception(
                    "Alert handler failed for %s on plugin %s",
                    alert_type, plugin_id,
                )

    def get_plugin_status(
        self, plugin_id: str
    ) -> Optional[Dict[str, Any]]:
        """Get the monitoring status of a plugin.

        Args:
            plugin_id: Unique identifier for the plugin.

        Returns:
            A status dictionary or None if not monitored.
        """
        with self._lock:
            return self._plugins.get(plugin_id)

    def get_all_status(self) -> Dict[str, Any]:
        """Get monitoring status for all plugins.

        Returns:
            A dictionary with ``total_plugins``, ``plugins`` list,
            and ``metrics`` summary.
        """
        with self._lock:
            plugins = list(self._plugins.values())
            return {
                "total_plugins": len(plugins),
                "plugins": plugins,
                "metrics": self._metrics.get_stats(),
            }

    def get_stats(self) -> Dict[str, Any]:
        """Get monitor statistics.

        Returns:
            A dictionary with plugin count and metrics summary.
        """
        return self.get_all_status()