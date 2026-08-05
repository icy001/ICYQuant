"""Load balancer for ICYQuant Service Mesh.

Provides ``LoadBalancer`` with multiple strategies: round robin,
weighted, least request, least latency, and consistent hash.
"""

from __future__ import annotations

import hashlib
import logging
import random
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class LoadBalancerStrategy:
    """Load balancing strategy types."""

    ROUND_ROBIN = "round_robin"
    WEIGHTED = "weighted"
    LEAST_REQUEST = "least_request"
    LEAST_LATENCY = "least_latency"
    CONSISTENT_HASH = "consistent_hash"


class LoadBalancer:
    """Load balancer for selecting endpoints."""

    def __init__(
        self,
        strategy: str = LoadBalancerStrategy.ROUND_ROBIN,
    ) -> None:
        self._lock = threading.RLock()
        self._strategy = strategy
        self._rr_index = 0
        self._request_counts: Dict[str, int] = {}
        self._latency_ms: Dict[str, float] = {}
        self._endpoint_stats: Dict[str, Dict[str, Any]] = {}
        self._select_count = 0

    @property
    def strategy(self) -> str:
        return self._strategy

    def set_strategy(self, strategy: str) -> None:
        with self._lock:
            self._strategy = strategy

    def select(
        self,
        endpoints: List[str],
        key: str = "",
        weights: Optional[Dict[str, float]] = None,
    ) -> Optional[str]:
        """Select an endpoint using the configured strategy."""
        if not endpoints:
            return None

        with self._lock:
            self._select_count += 1
            strategy = self._strategy

        if strategy == LoadBalancerStrategy.WEIGHTED and weights:
            return self._select_weighted(
                endpoints, weights
            )
        elif strategy == LoadBalancerStrategy.LEAST_REQUEST:
            return self._select_least_request(endpoints)
        elif strategy == LoadBalancerStrategy.LEAST_LATENCY:
            return self._select_least_latency(endpoints)
        elif strategy == LoadBalancerStrategy.CONSISTENT_HASH:
            return self._select_consistent_hash(
                endpoints, key
            )
        else:
            return self._select_round_robin(endpoints)

    def _select_round_robin(
        self, endpoints: List[str]
    ) -> str:
        with self._lock:
            idx = self._rr_index % len(endpoints)
            self._rr_index += 1
            return endpoints[idx]

    def _select_weighted(
        self,
        endpoints: List[str],
        weights: Dict[str, float],
    ) -> str:
        total = sum(
            weights.get(ep, 1.0) for ep in endpoints
        )
        if total <= 0:
            return endpoints[0]
        target = random.uniform(0, total)
        cumulative = 0.0
        for ep in endpoints:
            cumulative += weights.get(ep, 1.0)
            if cumulative >= target:
                return ep
        return endpoints[-1]

    def _select_least_request(
        self, endpoints: List[str]
    ) -> str:
        with self._lock:
            best_ep = endpoints[0]
            best_count = self._request_counts.get(
                best_ep, 0
            )
            for ep in endpoints[1:]:
                count = self._request_counts.get(ep, 0)
                if count < best_count:
                    best_count = count
                    best_ep = ep
            self._request_counts[best_ep] = (
                self._request_counts.get(best_ep, 0) + 1
            )
            return best_ep

    def _select_least_latency(
        self, endpoints: List[str]
    ) -> str:
        with self._lock:
            best_ep = endpoints[0]
            best_lat = self._latency_ms.get(
                best_ep, float("inf")
            )
            for ep in endpoints[1:]:
                lat = self._latency_ms.get(ep, float("inf"))
                if lat < best_lat:
                    best_lat = lat
                    best_ep = ep
            return best_ep

    def _select_consistent_hash(
        self, endpoints: List[str], key: str
    ) -> str:
        if not key:
            return endpoints[0]
        hash_val = int(
            hashlib.md5(key.encode()).hexdigest(), 16
        )
        idx = hash_val % len(endpoints)
        return endpoints[idx]

    def record_result(
        self,
        endpoint: str,
        success: bool = True,
        latency_ms: float = 0.0,
    ) -> None:
        with self._lock:
            if endpoint not in self._endpoint_stats:
                self._endpoint_stats[endpoint] = {
                    "successes": 0,
                    "failures": 0,
                    "total_latency": 0.0,
                }
            stats = self._endpoint_stats[endpoint]
            if success:
                stats["successes"] += 1
            else:
                stats["failures"] += 1
            if latency_ms > 0:
                stats["total_latency"] += latency_ms
                self._latency_ms[endpoint] = latency_ms

    def get_endpoint_stats(
        self, endpoint: str
    ) -> Dict[str, Any]:
        with self._lock:
            stats = self._endpoint_stats.get(endpoint, {})
            total = stats.get("successes", 0) + stats.get(
                "failures", 0
            )
            return {
                "endpoint": endpoint,
                "total": total,
                "success_rate": (
                    stats.get("successes", 0) / total
                    if total > 0
                    else 0.0
                ),
                "avg_latency_ms": (
                    stats.get("total_latency", 0.0) / total
                    if total > 0
                    else 0.0
                ),
            }

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "strategy": self._strategy,
                "select_count": self._select_count,
                "endpoint_count": len(
                    self._endpoint_stats
                ),
                "rr_index": self._rr_index,
                "request_counts": dict(self._request_counts),
            }