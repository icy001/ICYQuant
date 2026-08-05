"""Loader metrics for the plugin loader subsystem.

Provides thread-safe metrics collection for loader components,
tracking discovery, load, unload, reload, import, scan, and
dependency resolution operations as counters and histograms.

Counter names:

- ``icyquant_plugin_discovery_total``
- ``icyquant_plugin_load_total``
- ``icyquant_plugin_reload_total``
- ``icyquant_plugin_unload_total``
- ``icyquant_plugin_import_total``
- ``icyquant_plugin_scan_total``
- ``icyquant_plugin_dependency_resolution_total``

Histogram names:

- ``icyquant_plugin_import_seconds``
- ``icyquant_plugin_scan_seconds``
- ``icyquant_plugin_dependency_resolution_seconds``
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

DISCOVERY_COUNTER = "icyquant_plugin_discovery_total"
LOAD_COUNTER = "icyquant_plugin_load_total"
RELOAD_COUNTER = "icyquant_plugin_reload_total"
UNLOAD_COUNTER = "icyquant_plugin_unload_total"
IMPORT_COUNTER = "icyquant_plugin_import_total"
SCAN_COUNTER = "icyquant_plugin_scan_total"
DEP_RESOLUTION_COUNTER = "icyquant_plugin_dependency_resolution_total"
ERROR_COUNTER = "icyquant_plugin_loader_errors_total"

IMPORT_HISTOGRAM = "icyquant_plugin_import_seconds"
SCAN_HISTOGRAM = "icyquant_plugin_scan_seconds"
DEP_RESOLUTION_HISTOGRAM = "icyquant_plugin_dependency_resolution_seconds"


class LoaderMetrics:
    """Thread-safe metrics collection for the plugin loader.

    Maintains counters and histograms keyed by plugin id. All
    operations are guarded by a single lock for thread safety.

    Counters track the number of operations. Histograms track
    the duration of operations in seconds and can be queried
    for summary statistics (avg, min, max, count).
    """

    def __init__(self) -> None:
        self._counters: Dict[str, Dict[str, int]] = defaultdict(
            lambda: defaultdict(int)
        )
        self._histograms: Dict[str, Dict[str, List[float]]] = defaultdict(
            lambda: defaultdict(list)
        )
        self._lock = threading.RLock()

    def record_discovery(
        self, plugin_id: str, duration: float
    ) -> None:
        """Record a plugin discovery event.

        Args:
            plugin_id: The plugin identifier.
            duration: Duration of the discovery operation in seconds.
        """
        with self._lock:
            self._counters[DISCOVERY_COUNTER][plugin_id] += 1
            self._histograms[DISCOVERY_COUNTER][plugin_id].append(
                float(duration)
            )

    def record_load(
        self, plugin_id: str, duration: float
    ) -> None:
        """Record a successful plugin load event.

        Args:
            plugin_id: The plugin identifier.
            duration: Duration of the load operation in seconds.
        """
        with self._lock:
            self._counters[LOAD_COUNTER][plugin_id] += 1
            self._histograms[IMPORT_HISTOGRAM][plugin_id].append(
                float(duration)
            )

    def record_reload(
        self, plugin_id: str, duration: float
    ) -> None:
        """Record a plugin reload event.

        Args:
            plugin_id: The plugin identifier.
            duration: Duration of the reload operation in seconds.
        """
        with self._lock:
            self._counters[RELOAD_COUNTER][plugin_id] += 1
            self._histograms["icyquant_plugin_reload_seconds"][
                plugin_id
            ].append(float(duration))

    def record_unload(
        self, plugin_id: str, duration: float
    ) -> None:
        """Record a plugin unload event.

        Args:
            plugin_id: The plugin identifier.
            duration: Duration of the unload operation in seconds.
        """
        with self._lock:
            self._counters[UNLOAD_COUNTER][plugin_id] += 1
            self._histograms["icyquant_plugin_unload_seconds"][
                plugin_id
            ].append(float(duration))

    def record_import(
        self, plugin_id: str, duration: float
    ) -> None:
        """Record a module import event.

        Args:
            plugin_id: The plugin identifier.
            duration: Duration of the import operation in seconds.
        """
        with self._lock:
            self._counters[IMPORT_COUNTER][plugin_id] += 1
            self._histograms[IMPORT_HISTOGRAM][plugin_id].append(
                float(duration)
            )

    def record_scan(
        self, plugin_id: str, duration: float
    ) -> None:
        """Record a directory scan event.

        Args:
            plugin_id: The plugin identifier or scan path.
            duration: Duration of the scan operation in seconds.
        """
        with self._lock:
            self._counters[SCAN_COUNTER][plugin_id] += 1
            self._histograms[SCAN_HISTOGRAM][plugin_id].append(
                float(duration)
            )

    def record_dependency_resolution(
        self, plugin_id: str, duration: float
    ) -> None:
        """Record a dependency resolution event.

        Args:
            plugin_id: The plugin identifier.
            duration: Duration of the resolution operation in seconds.
        """
        with self._lock:
            self._counters[DEP_RESOLUTION_COUNTER][plugin_id] += 1
            self._histograms[DEP_RESOLUTION_HISTOGRAM][
                plugin_id
            ].append(float(duration))

    def record_error(
        self, plugin_id: str, error: str
    ) -> None:
        """Record a loader error event.

        Args:
            plugin_id: The plugin identifier.
            error: Description of the error.
        """
        with self._lock:
            self._counters[ERROR_COUNTER][plugin_id] += 1
        logger.warning(
            "Loader error for plugin '%s': %s", plugin_id, error or "unknown"
        )

    def get_counter(self, name: str) -> int:
        """Return the sum of a named counter across all plugin ids.

        Args:
            name: Counter name (e.g. ``icyquant_plugin_load_total``).

        Returns:
            The total count across all plugin ids.
        """
        with self._lock:
            entries = self._counters.get(name, {})
            return int(sum(entries.values()))

    def get_histogram(self, name: str) -> Dict[str, Any]:
        """Return summary statistics for a named histogram.

        Args:
            name: Histogram name (e.g. ``icyquant_plugin_import_seconds``).

        Returns:
            A dictionary with ``avg``, ``min``, ``max``, ``count``,
            and ``by_key`` keys. Empty histograms return zeroed stats.
        """
        with self._lock:
            by_key: Dict[str, Dict[str, float]] = {}
            all_values: List[float] = []
            for key, values in self._histograms.get(name, {}).items():
                if not values:
                    by_key[key] = {
                        "avg": 0.0,
                        "min": 0.0,
                        "max": 0.0,
                        "count": 0,
                    }
                    continue
                by_key[key] = {
                    "avg": sum(values) / len(values),
                    "min": min(values),
                    "max": max(values),
                    "count": len(values),
                }
                all_values.extend(values)

            if not all_values:
                return {
                    "avg": 0.0,
                    "min": 0.0,
                    "max": 0.0,
                    "count": 0,
                    "by_key": by_key,
                }

            return {
                "avg": sum(all_values) / len(all_values),
                "min": min(all_values),
                "max": max(all_values),
                "count": len(all_values),
                "by_key": by_key,
            }

    def snapshot(self) -> Dict[str, Any]:
        """Return a point-in-time snapshot of all metrics.

        Returns:
            A dictionary with counter totals, raw counter entries,
            and histogram summaries.
        """
        with self._lock:
            counters = {
                name: dict(entries)
                for name, entries in self._counters.items()
            }
            counter_totals = {
                name: int(sum(entries.values()))
                for name, entries in counters.items()
            }
            histogram_summaries = {
                name: self.get_histogram(name)
                for name in self._histograms
            }

        return {
            "counters": counters,
            "counter_totals": counter_totals,
            "histograms": histogram_summaries,
        }

    def reset(self) -> None:
        """Reset all metrics to zero."""
        with self._lock:
            self._counters.clear()
            self._histograms.clear()
        logger.info("Loader metrics reset.")

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the metrics system.

        Returns:
            A dictionary with counter and histogram summaries.
        """
        with self._lock:
            counter_names = list(self._counters.keys())
            histogram_names = list(self._histograms.keys())

        return {
            "counter_count": len(counter_names),
            "histogram_count": len(histogram_names),
            "counters": {
                name: self.get_counter(name)
                for name in counter_names
            },
            "histograms": {
                name: self.get_histogram(name)
                for name in histogram_names
            },
        }