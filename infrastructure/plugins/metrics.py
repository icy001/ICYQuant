"""Plugin metrics tracking.

Provides thread-safe metrics collection for the ICYQuant plugin framework,
tracking plugin lifecycle events, load durations, and evaluation performance.

Metrics:
- icyquant_plugin_total
- icyquant_plugin_loaded_total
- icyquant_plugin_failed_total
- icyquant_plugin_reload_total
- icyquant_plugin_load_duration_seconds
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

CounterKey = str
GaugeKey = str
HistogramKey = str


class PluginMetrics:
    """Tracks plugin-level metrics for observability.

    Provides counters, gauges, and histograms for monitoring
    plugin lifecycle, performance, and health. Thread-safe via
    a reentrant lock.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counters: Dict[str, Dict[CounterKey, float]] = defaultdict(dict)
        self._gauges: Dict[str, Dict[GaugeKey, float]] = defaultdict(dict)
        self._histograms: Dict[str, Dict[HistogramKey, Dict[str, float]]] = defaultdict(dict)
        self._timers: Dict[str, List[float]] = defaultdict(list)

    def record_load(self, plugin_id: str, duration_seconds: float) -> None:
        """Record a successful plugin load.

        Args:
            plugin_id: The unique plugin identifier.
            duration_seconds: Time taken to load the plugin.
        """
        with self._lock:
            self._increment_counter("icyquant_plugin_total", plugin_id)
            self._increment_counter("icyquant_plugin_loaded_total", plugin_id)
            self._record_histogram("icyquant_plugin_load_duration_seconds", plugin_id, duration_seconds)
            logger.debug(
                "Plugin '%s' loaded in %.4fs.", plugin_id, duration_seconds
            )

    def record_unload(self, plugin_id: str) -> None:
        """Record a plugin unload event.

        Args:
            plugin_id: The unique plugin identifier.
        """
        with self._lock:
            self._increment_counter("icyquant_plugin_total", plugin_id)
            self._set_gauge("icyquant_plugin_loaded_total", plugin_id, 0)
            logger.debug("Plugin '%s' unloaded.", plugin_id)

    def record_fail(self, plugin_id: str, error: str = "") -> None:
        """Record a plugin failure.

        Args:
            plugin_id: The unique plugin identifier.
            error: Optional error description.
        """
        with self._lock:
            self._increment_counter("icyquant_plugin_failed_total", plugin_id)
            logger.warning(
                "Plugin '%s' failed: %s", plugin_id, error or "unknown error"
            )

    def record_reload(self, plugin_id: str, duration_seconds: float) -> None:
        """Record a plugin reload event.

        Args:
            plugin_id: The unique plugin identifier.
            duration_seconds: Time taken to reload the plugin.
        """
        with self._lock:
            self._increment_counter("icyquant_plugin_reload_total", plugin_id)
            self._record_histogram("icyquant_plugin_load_duration_seconds", plugin_id, duration_seconds)
            logger.debug(
                "Plugin '%s' reloaded in %.4fs.", plugin_id, duration_seconds
            )

    def record_state_change(
        self, plugin_id: str, old_state: str, new_state: str
    ) -> None:
        """Record a plugin state transition.

        Args:
            plugin_id: The unique plugin identifier.
            old_state: Previous lifecycle state.
            new_state: New lifecycle state.
        """
        with self._lock:
            self._increment_counter("icyquant_plugin_total", plugin_id)
            state_counter = f"icyquant_plugin_state_{new_state}_total"
            self._increment_counter(state_counter, plugin_id)
            logger.debug(
                "Plugin '%s' state changed: %s -> %s",
                plugin_id,
                old_state,
                new_state,
            )

    def record_evaluation(
        self, plugin_id: str, duration_seconds: float, success: bool = True
    ) -> None:
        """Record a plugin evaluation (e.g., health check, hook execution).

        Args:
            plugin_id: The unique plugin identifier.
            duration_seconds: Duration of the evaluation.
            success: Whether the evaluation succeeded.
        """
        with self._lock:
            metric_name = "icyquant_plugin_evaluation_duration_seconds"
            self._record_histogram(metric_name, plugin_id, duration_seconds)
            if success:
                self._increment_counter(
                    "icyquant_plugin_evaluation_success_total", plugin_id
                )
            else:
                self._increment_counter(
                    "icyquant_plugin_evaluation_failure_total", plugin_id
                )

    def snapshot(self) -> Dict[str, Any]:
        """Return a point-in-time snapshot of all metrics.

        Returns:
            Dictionary containing counters, gauges, and histogram data.
        """
        with self._lock:
            return {
                "counters": {
                    name: dict(entries)
                    for name, entries in self._counters.items()
                },
                "gauges": {
                    name: dict(entries)
                    for name, entries in self._gauges.items()
                },
                "histograms": {
                    name: {
                        key: dict(values)
                        for key, values in hist_data.items()
                    }
                    for name, hist_data in self._histograms.items()
                },
            }

    def get_counter(self, name: str) -> int:
        """Get the sum of a named counter across all plugins.

        Args:
            name: Counter metric name.

        Returns:
            Sum of all counter values.
        """
        with self._lock:
            entries = self._counters.get(name, {})
            return int(sum(entries.values()))

    def get_gauge(self, name: str) -> float:
        """Get the sum of a named gauge across all plugins.

        Args:
            name: Gauge metric name.

        Returns:
            Sum of all gauge values.
        """
        with self._lock:
            entries = self._gauges.get(name, {})
            return float(sum(entries.values()))

    def get_histogram(self, name: str) -> Dict[str, float]:
        """Get histogram summary statistics for a named metric.

        Returns average, min, max, and count across all observations.

        Args:
            name: Histogram metric name.

        Returns:
            Dictionary with keys: avg, min, max, count.
        """
        with self._lock:
            all_values: List[float] = []
            for plugin_data in self._histograms.get(name, {}).values():
                if "value" in plugin_data:
                    all_values.append(plugin_data["value"])
                if "values" in plugin_data:
                    all_values.extend(plugin_data["values"])
            if not all_values:
                return {"avg": 0.0, "min": 0.0, "max": 0.0, "count": 0}
            return {
                "avg": sum(all_values) / len(all_values),
                "min": min(all_values),
                "max": max(all_values),
                "count": len(all_values),
            }

    def reset(self) -> None:
        """Reset all metrics to zero."""
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._timers.clear()
            logger.info("Plugin metrics reset.")

    def get_stats(self) -> Dict[str, Any]:
        """Get summary statistics of the metrics system itself.

        Returns:
            Dictionary with counts of tracked metrics.
        """
        with self._lock:
            return {
                "counter_count": len(self._counters),
                "gauge_count": len(self._gauges),
                "histogram_count": len(self._histograms),
                "counters": {
                    name: int(sum(entries.values()))
                    for name, entries in self._counters.items()
                },
                "gauges": {
                    name: float(sum(entries.values()))
                    for name, entries in self._gauges.items()
                },
                "histograms": {
                    name: self.get_histogram(name)
                    for name in self._histograms
                },
            }

    # ── Internal helpers ──

    @staticmethod
    def _make_key(labels: Optional[Dict[str, str]]) -> str:
        if not labels:
            return "__total__"
        parts = [f"{k}={v}" for k, v in sorted(labels.items())]
        return ",".join(parts)

    def _increment_counter(
        self, name: str, plugin_id: str, value: float = 1.0
    ) -> None:
        key = self._make_key({"plugin": plugin_id})
        if name not in self._counters:
            self._counters[name] = {}
        self._counters[name][key] = self._counters[name].get(key, 0.0) + value

    def _set_gauge(
        self, name: str, plugin_id: str, value: float
    ) -> None:
        key = self._make_key({"plugin": plugin_id})
        if name not in self._gauges:
            self._gauges[name] = {}
        self._gauges[name][key] = value

    def _record_histogram(
        self, name: str, plugin_id: str, value: float
    ) -> None:
        key = self._make_key({"plugin": plugin_id})
        if name not in self._histograms:
            self._histograms[name] = {}
        if key not in self._histograms[name]:
            self._histograms[name][key] = {
                "count": 0,
                "sum": 0.0,
                "min": float("inf"),
                "max": float("-inf"),
                "values": [],
            }
        entry = self._histograms[name][key]
        entry["count"] += 1
        entry["sum"] += value
        entry["min"] = min(entry["min"], value)
        entry["max"] = max(entry["max"], value)
        entry["values"].append(value)
        entry["value"] = value