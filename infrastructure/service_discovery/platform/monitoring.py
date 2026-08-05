"""Platform metrics and monitoring for ICYQuant service discovery.

Provides ``PlatformMetrics`` for tracking platform-level counters,
gauges, and histograms covering runtime operations, cluster sync,
topology, gateway requests, and reload events.

Metrics:
- icyquant_discovery_runtime_total
- icyquant_service_topology_total
- icyquant_service_snapshot_total
- icyquant_cluster_sync_total
- icyquant_discovery_gateway_requests_total
- icyquant_runtime_reload_total
"""

from __future__ import annotations

import logging
import threading
from collections import defaultdict
from typing import Any, Dict, List

logger = logging.getLogger(__name__)


class PlatformMetrics:
    """Tracks platform-level metrics for service discovery.

    Provides counters, gauges, and histograms for monitoring
    runtime operations, cluster synchronization, topology,
    gateway requests, and reload events.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counters: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._gauges: Dict[str, Dict[str, float]] = defaultdict(dict)
        self._histograms: Dict[
            str, Dict[str, Dict[str, float]]
        ] = defaultdict(dict)
        self._observations: Dict[str, List[float]] = defaultdict(list)
        self._recent_events: List[Dict[str, Any]] = []
        self._max_events = 500

    def record_runtime(
        self, event: str, service_name: str = "", duration: float = 0.0
    ) -> None:
        with self._lock:
            self._increment_counter(
                "icyquant_discovery_runtime_total", event or "unknown"
            )
            self._record_event("runtime", event, service_name, duration)

    def record_topology(
        self, operation: str, node_count: int = 0
    ) -> None:
        with self._lock:
            self._increment_counter(
                "icyquant_service_topology_total", operation or "unknown"
            )
            self._set_gauge(
                "icyquant_service_topology_node_count",
                "nodes",
                float(node_count),
            )
            self._record_event("topology", operation)

    def record_snapshot(
        self, operation: str, service_count: int = 0
    ) -> None:
        with self._lock:
            self._increment_counter(
                "icyquant_service_snapshot_total", operation or "unknown"
            )
            self._record_event("snapshot", operation)

    def record_cluster_sync(
        self, node_id: str, direction: str = "sync"
    ) -> None:
        with self._lock:
            self._increment_counter(
                "icyquant_cluster_sync_total", direction or "sync"
            )
            self._record_event("cluster_sync", direction, node_id)

    def record_gateway_request(
        self,
        endpoint: str,
        method: str = "GET",
        status_code: int = 200,
        duration: float = 0.0,
    ) -> None:
        with self._lock:
            self._increment_counter(
                "icyquant_discovery_gateway_requests_total",
                endpoint or "unknown",
            )
            self._record_histogram(
                "icyquant_discovery_gateway_latency_seconds",
                endpoint or "unknown",
                float(duration),
            )
            self._record_event(
                "gateway", endpoint, f"{method} {status_code}", duration
            )

    def record_reload(
        self, component: str, success: bool, duration: float = 0.0
    ) -> None:
        with self._lock:
            self._increment_counter(
                "icyquant_runtime_reload_total", component or "unknown"
            )
            self._record_histogram(
                "icyquant_runtime_reload_duration_seconds",
                component or "unknown",
                float(duration),
            )
            self._record_event(
                "reload", component, "success" if success else "failure", duration
            )

    def snapshot(self) -> Dict[str, Any]:
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
                "recent_events": list(self._recent_events),
                "timestamp": self._now_iso(),
            }

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._histograms.clear()
            self._observations.clear()
            self._recent_events.clear()

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "counter_count": len(self._counters),
                "gauge_count": len(self._gauges),
                "histogram_count": len(self._histograms),
                "event_count": len(self._recent_events),
                "counters": {
                    name: int(sum(entries.values()))
                    for name, entries in self._counters.items()
                },
            }

    @staticmethod
    def _make_key(label: str) -> str:
        return label or "__total__"

    def _increment_counter(
        self, name: str, label: str, value: float = 1.0
    ) -> None:
        key = self._make_key(label)
        self._counters[name][key] = (
            self._counters[name].get(key, 0.0) + value
        )

    def _set_gauge(self, name: str, label: str, value: float) -> None:
        key = self._make_key(label)
        self._gauges[name][key] = value

    def _record_histogram(
        self, name: str, label: str, value: float
    ) -> None:
        key = self._make_key(label)
        entry = self._histograms[name].get(key)
        if entry is None:
            entry = {
                "count": 0,
                "sum": 0.0,
                "min": float("inf"),
                "max": float("-inf"),
            }
            self._histograms[name][key] = entry
        entry["count"] += 1
        entry["sum"] += value
        entry["min"] = min(entry["min"], value)
        entry["max"] = max(entry["max"], value)
        self._observations[name].append(value)

    def _record_event(
        self,
        category: str,
        detail: str,
        extra: str = "",
        duration: float = 0.0,
    ) -> None:
        self._recent_events.append(
            {
                "category": category,
                "detail": detail,
                "extra": extra,
                "duration": duration,
                "timestamp": self._now_iso(),
            }
        )
        if len(self._recent_events) > self._max_events:
            self._recent_events = self._recent_events[-self._max_events:]

    @staticmethod
    def _now_iso() -> str:
        from datetime import datetime

        return datetime.utcnow().isoformat()

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"PlatformMetrics(counters={len(self._counters)}, "
                f"events={len(self._recent_events)})"
            )
