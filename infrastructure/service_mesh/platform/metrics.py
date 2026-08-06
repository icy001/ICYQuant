"""Platform Metrics for ICYQuant Service Mesh Platform.

Provides ``PlatformMetrics`` for tracking service mesh platform
operational metrics including runtime, plugin, snapshot, restore,
upgrade, injection, and control API counters.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class PlatformMetrics:
    """Collects and reports service mesh platform metrics."""

    RUNTIME_TOTAL = "icyquant_mesh_runtime_total"
    PLUGIN_TOTAL = "icyquant_mesh_plugin_total"
    SNAPSHOT_TOTAL = "icyquant_mesh_snapshot_total"
    RESTORE_TOTAL = "icyquant_mesh_restore_total"
    UPGRADE_TOTAL = "icyquant_mesh_upgrade_total"
    INJECTION_TOTAL = "icyquant_mesh_injection_total"
    CONTROL_API_TOTAL = "icyquant_mesh_control_api_total"

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._counters: Dict[str, int] = {}
        self._gauges: Dict[str, float] = {}
        self._timers: Dict[str, List[float]] = {}
        self._labels: Dict[str, Dict[str, str]] = {}
        self._start_time = time.monotonic()
        self._register_defaults()

    def _register_defaults(self) -> None:
        for metric in [
            self.RUNTIME_TOTAL,
            self.PLUGIN_TOTAL,
            self.SNAPSHOT_TOTAL,
            self.RESTORE_TOTAL,
            self.UPGRADE_TOTAL,
            self.INJECTION_TOTAL,
            self.CONTROL_API_TOTAL,
        ]:
            self._counters[metric] = 0

    def increment_counter(
        self,
        name: str,
        value: int = 1,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        with self._lock:
            if name not in self._counters:
                self._counters[name] = 0
            self._counters[name] += value
            if labels:
                self._labels[name] = labels

    def set_gauge(
        self,
        name: str,
        value: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        with self._lock:
            self._gauges[name] = value
            if labels:
                self._labels[name] = labels

    def record_timer(
        self,
        name: str,
        duration_s: float,
        labels: Optional[Dict[str, str]] = None,
    ) -> None:
        with self._lock:
            if name not in self._timers:
                self._timers[name] = []
            self._timers[name].append(duration_s)
            if len(self._timers[name]) > 1000:
                self._timers[name] = self._timers[name][-1000:]
            if labels:
                self._labels[name] = labels

    def increment_runtime_total(
        self, labels: Optional[Dict[str, str]] = None
    ) -> None:
        self.increment_counter(self.RUNTIME_TOTAL, labels=labels)

    def increment_plugin_total(
        self, labels: Optional[Dict[str, str]] = None
    ) -> None:
        self.increment_counter(self.PLUGIN_TOTAL, labels=labels)

    def increment_snapshot_total(
        self, labels: Optional[Dict[str, str]] = None
    ) -> None:
        self.increment_counter(self.SNAPSHOT_TOTAL, labels=labels)

    def increment_restore_total(
        self, labels: Optional[Dict[str, str]] = None
    ) -> None:
        self.increment_counter(self.RESTORE_TOTAL, labels=labels)

    def increment_upgrade_total(
        self, labels: Optional[Dict[str, str]] = None
    ) -> None:
        self.increment_counter(self.UPGRADE_TOTAL, labels=labels)

    def increment_injection_total(
        self, labels: Optional[Dict[str, str]] = None
    ) -> None:
        self.increment_counter(self.INJECTION_TOTAL, labels=labels)

    def increment_control_api_total(
        self, labels: Optional[Dict[str, str]] = None
    ) -> None:
        self.increment_counter(self.CONTROL_API_TOTAL, labels=labels)

    def get_counter(self, name: str) -> int:
        with self._lock:
            return self._counters.get(name, 0)

    def get_gauge(self, name: str) -> float:
        with self._lock:
            return self._gauges.get(name, 0.0)

    def get_timers(self, name: str) -> List[float]:
        with self._lock:
            return list(self._timers.get(name, []))

    def get_summary(self) -> Dict[str, Any]:
        with self._lock:
            uptime = time.monotonic() - self._start_time
            timer_stats: Dict[str, Dict[str, float]] = {}
            for name, durations in self._timers.items():
                if durations:
                    timer_stats[name] = {
                        "count": len(durations),
                        "avg": sum(durations) / len(durations),
                        "min": min(durations),
                        "max": max(durations),
                    }
            return {
                "uptime_s": uptime,
                "counters": dict(self._counters),
                "gauges": dict(self._gauges),
                "timer_stats": timer_stats,
                "labels": dict(self._labels),
            }

    def get_stats(self) -> Dict[str, Any]:
        return self.get_summary()

    def reset(self) -> None:
        with self._lock:
            self._counters.clear()
            self._gauges.clear()
            self._timers.clear()
            self._labels.clear()
            self._register_defaults()
            self._start_time = time.monotonic()
