"""Metrics aggregator for ICYQuant Service Mesh.

Provides ``MetricsAggregator`` for aggregating metrics across
services, namespaces, clusters, and globally, with rolling
window, percentile, and EWMA support.
"""

from __future__ import annotations

import logging
import threading
import time
from collections import deque
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


class RollingWindow:
    """Rolling window time-series buffer."""

    def __init__(self, window_s: float = 60.0, max_samples: int = 10000) -> None:
        self._window_s = window_s
        self._max_samples = max_samples
        self._samples: deque = deque()
        self._lock = threading.Lock()

    def add(self, value: float, timestamp: Optional[float] = None) -> None:
        ts = timestamp or time.monotonic()
        with self._lock:
            self._samples.append((ts, value))
            self._prune(ts)

    def _prune(self, now: float) -> None:
        cutoff = now - self._window_s
        while self._samples and self._samples[0][0] < cutoff:
            self._samples.popleft()
        if len(self._samples) > self._max_samples:
            while len(self._samples) > self._max_samples:
                self._samples.popleft()

    def values(self) -> List[float]:
        with self._lock:
            now = time.monotonic()
            self._prune(now)
            return [v for _, v in self._samples]

    @property
    def count(self) -> int:
        with self._lock:
            return len(self._samples)

    @property
    def window_s(self) -> float:
        return self._window_s

    def stats(self) -> Dict[str, float]:
        vals = self.values()
        if not vals:
            return {"count": 0, "min": 0, "max": 0, "avg": 0, "sum": 0}
        return {
            "count": len(vals),
            "min": min(vals),
            "max": max(vals),
            "avg": sum(vals) / len(vals),
            "sum": sum(vals),
        }

    def percentile(self, p: float) -> float:
        vals = self.values()
        if not vals:
            return 0.0
        sorted_vals = sorted(vals)
        k = (len(sorted_vals) - 1) * p / 100.0
        f = int(k)
        c = min(f + 1, len(sorted_vals) - 1)
        if f == c:
            return sorted_vals[f]
        return sorted_vals[f] + (sorted_vals[c] - sorted_vals[f]) * (k - f)

    def clear(self) -> None:
        with self._lock:
            self._samples.clear()


class EWMA:
    """Exponentially Weighted Moving Average."""

    def __init__(self, alpha: float = 0.3) -> None:
        self._alpha = min(max(0.0, alpha), 1.0)
        self._value: Optional[float] = None
        self._lock = threading.Lock()

    def update(self, value: float) -> float:
        with self._lock:
            if self._value is None:
                self._value = value
            else:
                self._value = self._alpha * value + (1 - self._alpha) * self._value
            return self._value

    @property
    def value(self) -> float:
        with self._lock:
            return self._value or 0.0

    def reset(self) -> None:
        with self._lock:
            self._value = None


class AggregationScope(str):
    """Aggregation scope levels."""

    SERVICE = "service"
    NAMESPACE = "namespace"
    CLUSTER = "cluster"
    GLOBAL = "global"


class MetricsAggregator:
    """Aggregates metrics across multiple scopes."""

    def __init__(
        self,
        window_s: float = 60.0,
        enable_ewma: bool = True,
        ewma_alpha: float = 0.3,
    ) -> None:
        self._window_s = window_s
        self._enable_ewma = enable_ewma
        self._ewma_alpha = ewma_alpha
        self._lock = threading.RLock()
        self._service_windows: Dict[str, Dict[str, RollingWindow]] = {}
        self._namespace_windows: Dict[str, Dict[str, RollingWindow]] = {}
        self._cluster_windows: Dict[str, Dict[str, RollingWindow]] = {}
        self._global_windows: Dict[str, RollingWindow] = {}
        self._service_ewma: Dict[str, Dict[str, EWMA]] = {}
        self._namespace_ewma: Dict[str, Dict[str, EWMA]] = {}
        self._cluster_ewma: Dict[str, Dict[str, EWMA]] = {}
        self._global_ewma: Dict[str, EWMA] = {}
        self._aggregation_count = 0

    def _get_or_create_window(
        self,
        scope_dict: Dict[str, Dict[str, RollingWindow]],
        scope_key: str,
        metric: str,
    ) -> RollingWindow:
        if scope_key not in scope_dict:
            scope_dict[scope_key] = {}
        if metric not in scope_dict[scope_key]:
            scope_dict[scope_key][metric] = RollingWindow(self._window_s)
        return scope_dict[scope_key][metric]

    def _get_or_create_global_window(self, metric: str) -> RollingWindow:
        if metric not in self._global_windows:
            self._global_windows[metric] = RollingWindow(self._window_s)
        return self._global_windows[metric]

    def _get_or_create_ewma(
        self,
        scope_dict: Dict[str, Dict[str, EWMA]],
        scope_key: str,
        metric: str,
    ) -> Optional[EWMA]:
        if not self._enable_ewma:
            return None
        if scope_key not in scope_dict:
            scope_dict[scope_key] = {}
        if metric not in scope_dict[scope_key]:
            scope_dict[scope_key][metric] = EWMA(self._ewma_alpha)
        return scope_dict[scope_key][metric]

    def _get_or_create_global_ewma(self, metric: str) -> Optional[EWMA]:
        if not self._enable_ewma:
            return None
        if metric not in self._global_ewma:
            self._global_ewma[metric] = EWMA(self._ewma_alpha)
        return self._global_ewma[metric]

    def record(
        self,
        metric: str,
        value: float,
        service: str = "",
        namespace: str = "",
        cluster: str = "",
    ) -> None:
        with self._lock:
            self._aggregation_count += 1

            if service:
                w = self._get_or_create_window(self._service_windows, service, metric)
                w.add(value)
                ewma = self._get_or_create_ewma(self._service_ewma, service, metric)
                if ewma:
                    ewma.update(value)

            if namespace:
                w = self._get_or_create_window(self._namespace_windows, namespace, metric)
                w.add(value)
                ewma = self._get_or_create_ewma(self._namespace_ewma, namespace, metric)
                if ewma:
                    ewma.update(value)

            if cluster:
                w = self._get_or_create_window(self._cluster_windows, cluster, metric)
                w.add(value)
                ewma = self._get_or_create_ewma(self._cluster_ewma, cluster, metric)
                if ewma:
                    ewma.update(value)

            gw = self._get_or_create_global_window(metric)
            gw.add(value)
            gewma = self._get_or_create_global_ewma(metric)
            if gewma:
                gewma.update(value)

    def get_service_metric(self, service: str, metric: str) -> Dict[str, Any]:
        with self._lock:
            windows = self._service_windows.get(service, {})
            ewmas = self._service_ewma.get(service, {})
            window = windows.get(metric)
            ewma = ewmas.get(metric)
        result: Dict[str, Any] = {}
        if window:
            result["window"] = window.stats()
            result["p50"] = window.percentile(50)
            result["p99"] = window.percentile(99)
        if ewma:
            result["ewma"] = ewma.value
        return result

    def get_namespace_metric(self, namespace: str, metric: str) -> Dict[str, Any]:
        with self._lock:
            windows = self._namespace_windows.get(namespace, {})
            ewmas = self._namespace_ewma.get(namespace, {})
            window = windows.get(metric)
            ewma = ewmas.get(metric)
        result: Dict[str, Any] = {}
        if window:
            result["window"] = window.stats()
            result["p50"] = window.percentile(50)
            result["p99"] = window.percentile(99)
        if ewma:
            result["ewma"] = ewma.value
        return result

    def get_cluster_metric(self, cluster: str, metric: str) -> Dict[str, Any]:
        with self._lock:
            windows = self._cluster_windows.get(cluster, {})
            ewmas = self._cluster_ewma.get(cluster, {})
            window = windows.get(metric)
            ewma = ewmas.get(metric)
        result: Dict[str, Any] = {}
        if window:
            result["window"] = window.stats()
            result["p50"] = window.percentile(50)
            result["p99"] = window.percentile(99)
        if ewma:
            result["ewma"] = ewma.value
        return result

    def get_global_metric(self, metric: str) -> Dict[str, Any]:
        with self._lock:
            window = self._global_windows.get(metric)
            ewma = self._global_ewma.get(metric)
        result: Dict[str, Any] = {}
        if window:
            result["window"] = window.stats()
            result["p50"] = window.percentile(50)
            result["p99"] = window.percentile(99)
        if ewma:
            result["ewma"] = ewma.value
        return result

    def list_services(self) -> List[str]:
        with self._lock:
            return list(self._service_windows.keys())

    def list_namespaces(self) -> List[str]:
        with self._lock:
            return list(self._namespace_windows.keys())

    def list_metrics(self) -> List[str]:
        with self._lock:
            return list(self._global_windows.keys())

    def get_overview(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "service_count": len(self._service_windows),
                "namespace_count": len(self._namespace_windows),
                "cluster_count": len(self._cluster_windows),
                "metric_count": len(self._global_windows),
                "aggregation_count": self._aggregation_count,
                "window_s": self._window_s,
                "ewma_enabled": self._enable_ewma,
            }

    def get_stats(self) -> Dict[str, Any]:
        return self.get_overview()

    def clear(self) -> None:
        with self._lock:
            self._service_windows.clear()
            self._namespace_windows.clear()
            self._cluster_windows.clear()
            self._global_windows.clear()
            self._service_ewma.clear()
            self._namespace_ewma.clear()
            self._cluster_ewma.clear()
            self._global_ewma.clear()
            self._aggregation_count = 0
