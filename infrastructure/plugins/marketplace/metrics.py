"""Marketplace metrics collection.

Provides :class:`MarketplaceMetrics` for recording and reporting
marketplace operational metrics including installs, updates,
uninstalls, downloads, searches, rollbacks, and validations, with
thread-safe counter and histogram support.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import defaultdict
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

INSTALL_COUNTER = "icyquant_marketplace_install_total"
UPDATE_COUNTER = "icyquant_marketplace_update_total"
UNINSTALL_COUNTER = "icyquant_marketplace_uninstall_total"
DOWNLOAD_COUNTER = "icyquant_marketplace_download_total"
SEARCH_COUNTER = "icyquant_marketplace_search_total"
ROLLBACK_COUNTER = "icyquant_marketplace_rollback_total"
VALIDATION_COUNTER = "icyquant_marketplace_validation_total"
ERROR_COUNTER = "icyquant_marketplace_errors_total"

INSTALL_HISTOGRAM = "icyquant_marketplace_install_seconds"
UPDATE_HISTOGRAM = "icyquant_marketplace_update_seconds"
DOWNLOAD_HISTOGRAM = "icyquant_marketplace_download_seconds"
SEARCH_HISTOGRAM = "icyquant_marketplace_search_seconds"
ROLLBACK_HISTOGRAM = "icyquant_marketplace_rollback_seconds"


class MarketplaceMetrics:
    """Thread-safe metrics collection for the marketplace.

    Maintains counters and histograms keyed by plugin id.  All
    operations are guarded by a single lock for thread safety.

    Counters track the number of operations.  Histograms track
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

    def record_install(
        self, plugin_id: str, duration: float, success: bool
    ) -> None:
        """Record a plugin install event.

        Args:
            plugin_id: The plugin identifier.
            duration: Duration of the install operation in seconds.
            success: Whether the install succeeded.
        """
        with self._lock:
            self._counters[INSTALL_COUNTER][plugin_id] += 1
            if not success:
                self._counters[ERROR_COUNTER][plugin_id] += 1
            self._histograms[INSTALL_HISTOGRAM][plugin_id].append(
                float(duration)
            )

    def record_update(
        self, plugin_id: str, duration: float, success: bool
    ) -> None:
        """Record a plugin update event.

        Args:
            plugin_id: The plugin identifier.
            duration: Duration of the update operation in seconds.
            success: Whether the update succeeded.
        """
        with self._lock:
            self._counters[UPDATE_COUNTER][plugin_id] += 1
            if not success:
                self._counters[ERROR_COUNTER][plugin_id] += 1
            self._histograms[UPDATE_HISTOGRAM][plugin_id].append(
                float(duration)
            )

    def record_uninstall(
        self, plugin_id: str, success: bool
    ) -> None:
        """Record a plugin uninstall event.

        Args:
            plugin_id: The plugin identifier.
            success: Whether the uninstall succeeded.
        """
        with self._lock:
            self._counters[UNINSTALL_COUNTER][plugin_id] += 1
            if not success:
                self._counters[ERROR_COUNTER][plugin_id] += 1

    def record_download(
        self,
        plugin_id: str,
        size_bytes: int,
        duration: float,
    ) -> None:
        """Record a package download event.

        Args:
            plugin_id: The plugin identifier.
            size_bytes: Size of the downloaded package in bytes.
            duration: Duration of the download in seconds.
        """
        with self._lock:
            self._counters[DOWNLOAD_COUNTER][plugin_id] += 1
            self._histograms[DOWNLOAD_HISTOGRAM][plugin_id].append(
                float(duration)
            )

    def record_search(
        self, query: str, result_count: int
    ) -> None:
        """Record a search event.

        Args:
            query: The search query string.
            result_count: Number of results returned.
        """
        with self._lock:
            self._counters[SEARCH_COUNTER][query] += 1

    def record_rollback(
        self, plugin_id: str, success: bool
    ) -> None:
        """Record a plugin rollback event.

        Args:
            plugin_id: The plugin identifier.
            success: Whether the rollback succeeded.
        """
        with self._lock:
            self._counters[ROLLBACK_COUNTER][plugin_id] += 1
            if not success:
                self._counters[ERROR_COUNTER][plugin_id] += 1

    def record_validation(
        self, plugin_id: str, errors: int
    ) -> None:
        """Record a package validation event.

        Args:
            plugin_id: The plugin identifier.
            errors: Number of validation errors found.
        """
        with self._lock:
            self._counters[VALIDATION_COUNTER][plugin_id] += 1
            if errors > 0:
                self._counters[ERROR_COUNTER][plugin_id] += errors

    def get_counter(self, name: str) -> int:
        """Return the sum of a named counter across all plugin ids.

        Args:
            name: Counter name (e.g.
                ``icyquant_marketplace_install_total``).

        Returns:
            The total count across all plugin ids.
        """
        with self._lock:
            entries = self._counters.get(name, {})
            return int(sum(entries.values()))

    def get_histogram(self, name: str) -> Dict[str, Any]:
        """Return summary statistics for a named histogram.

        Args:
            name: Histogram name (e.g.
                ``icyquant_marketplace_install_seconds``).

        Returns:
            A dictionary with ``avg``, ``min``, ``max``, ``count``,
            and ``by_key`` keys.
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
            "timestamp": time.time(),
        }

    def reset(self) -> None:
        """Reset all metrics to zero."""
        with self._lock:
            self._counters.clear()
            self._histograms.clear()
        logger.info("Marketplace metrics reset")

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