"""Weighted router for ICYQuant Service Mesh.

Provides ``WeightedRouter`` for dynamic weight adjustment based on
health, latency, and request metrics. Supports static, dynamic,
latency-based, and health-based weight strategies.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class WeightedRouter:
    """Router with dynamic weight adjustment."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._weights: Dict[str, float] = {}
        self._health: Dict[str, bool] = {}
        self._latency_ms: Dict[str, float] = {}
        self._request_counts: Dict[str, int] = {}
        self._error_counts: Dict[str, int] = {}
        self._strategy = "dynamic"
        self._adjustment_count = 0

    def set_weight(
        self, endpoint: str, weight: float
    ) -> None:
        with self._lock:
            self._weights[endpoint] = max(0.0, weight)

    def set_strategy(self, strategy: str) -> None:
        with self._lock:
            self._strategy = strategy

    def set_health(
        self, endpoint: str, healthy: bool
    ) -> None:
        with self._lock:
            self._health[endpoint] = healthy
            if not healthy:
                self._weights[endpoint] = 0.0

    def record_latency(
        self, endpoint: str, latency_ms: float
    ) -> None:
        with self._lock:
            self._latency_ms[endpoint] = latency_ms

    def record_request(
        self, endpoint: str, success: bool = True
    ) -> None:
        with self._lock:
            self._request_counts[endpoint] = (
                self._request_counts.get(endpoint, 0) + 1
            )
            if not success:
                self._error_counts[endpoint] = (
                    self._error_counts.get(endpoint, 0) + 1
                )

    def get_weights(
        self, endpoints: List[str]
    ) -> Dict[str, float]:
        with self._lock:
            if self._strategy == "static":
                return self._get_static_weights(endpoints)
            elif self._strategy == "latency":
                return self._get_latency_weights(endpoints)
            elif self._strategy == "health":
                return self._get_health_weights(endpoints)
            else:
                return self._get_dynamic_weights(endpoints)

    def _get_static_weights(
        self, endpoints: List[str]
    ) -> Dict[str, float]:
        return {
            ep: self._weights.get(ep, 1.0)
            for ep in endpoints
        }

    def _get_dynamic_weights(
        self, endpoints: List[str]
    ) -> Dict[str, float]:
        weights = {}
        for ep in endpoints:
            base = self._weights.get(ep, 1.0)
            health_mult = (
                1.0
                if self._health.get(ep, True)
                else 0.0
            )
            error_count = self._error_counts.get(ep, 0)
            req_count = self._request_counts.get(ep, 1)
            error_rate = (
                error_count / req_count if req_count > 0 else 0
            )
            error_mult = max(0.1, 1.0 - error_rate)
            weights[ep] = base * health_mult * error_mult
        return weights

    def _get_latency_weights(
        self, endpoints: List[str]
    ) -> Dict[str, float]:
        weights = {}
        avg_latency = 0.0
        latency_count = 0
        for ep in endpoints:
            lat = self._latency_ms.get(ep, 0.0)
            if lat > 0:
                avg_latency += lat
                latency_count += 1
        if latency_count > 0:
            avg_latency /= latency_count
        for ep in endpoints:
            base = self._weights.get(ep, 1.0)
            lat = self._latency_ms.get(ep, avg_latency)
            if lat > 0 and avg_latency > 0:
                latency_mult = avg_latency / max(lat, 0.1)
            else:
                latency_mult = 1.0
            weights[ep] = base * latency_mult
        return weights

    def _get_health_weights(
        self, endpoints: List[str]
    ) -> Dict[str, float]:
        weights = {}
        for ep in endpoints:
            base = self._weights.get(ep, 1.0)
            healthy = self._health.get(ep, True)
            weights[ep] = base if healthy else 0.0
        return weights

    def adjust_weights(
        self,
        endpoints: List[str],
        healthy: Optional[Dict[str, bool]] = None,
    ) -> Dict[str, float]:
        """Adjust weights based on health status."""
        with self._lock:
            self._adjustment_count += 1
        if healthy:
            for ep, is_healthy in healthy.items():
                self.set_health(ep, is_healthy)
        return self.get_weights(endpoints)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "strategy": self._strategy,
                "endpoint_count": len(self._weights),
                "adjustment_count": self._adjustment_count,
                "weights": dict(self._weights),
                "health": dict(self._health),
                "latency_ms": dict(self._latency_ms),
            }