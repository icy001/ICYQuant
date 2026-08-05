"""Async load balancer selectors.

Provides ``LoadBalancerSelector`` abstract base class and concrete
implementations for round-robin, weighted, least-connection,
least-latency, random, and consistent-hash selection strategies.
"""

from __future__ import annotations

import asyncio
import logging
import random
import threading
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from ..instance import ServiceInstance
from .context import ResolveContext

logger = logging.getLogger(__name__)


class LoadBalancerSelector(ABC):
    """Abstract base class for async load balancer selectors."""

    @abstractmethod
    async def select(
        self,
        instances: List[ServiceInstance],
        context: Optional[ResolveContext] = None,
    ) -> Optional[ServiceInstance]:
        """Select a single instance from the provided list.

        Args:
            instances: Candidate instances (assumed already filtered).
            context: Optional resolution context for strategy parameters.

        Returns:
            The selected instance or None if the list is empty.
        """

    def get_stats(self) -> Dict[str, Any]:
        """Return selector statistics.

        Returns:
            A dictionary with selector statistics.
        """
        return {"selector": type(self).__name__}


class RoundRobinLoadBalancer(LoadBalancerSelector):
    """Selects instances in round-robin order.

    Thread-safe with ``threading.RLock``.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._index = 0

    async def select(
        self,
        instances: List[ServiceInstance],
        context: Optional[ResolveContext] = None,
    ) -> Optional[ServiceInstance]:
        if not instances:
            return None
        await asyncio.sleep(0)
        with self._lock:
            if self._index >= len(instances):
                self._index = 0
            selected = instances[self._index]
            self._index = (self._index + 1) % len(instances)
            return selected

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "selector": type(self).__name__,
                "current_index": self._index,
            }


class WeightedLoadBalancer(LoadBalancerSelector):
    """Selects an instance proportional to its weight.

    Uses weighted random selection. Instances with non-positive
    weight are excluded. Thread-safe.
    """

    def __init__(self) -> None:
        self._lock = threading.RLock()

    async def select(
        self,
        instances: List[ServiceInstance],
        context: Optional[ResolveContext] = None,
    ) -> Optional[ServiceInstance]:
        if not instances:
            return None
        await asyncio.sleep(0)
        with self._lock:
            candidates = [i for i in instances if i.weight > 0]
            if not candidates:
                return instances[0]
            weights = [i.weight for i in candidates]
            total = sum(weights)
            if total <= 0:
                return candidates[0]
            threshold = random.uniform(0, total)
            cumulative = 0.0
            for instance, weight in zip(candidates, weights):
                cumulative += weight
                if cumulative >= threshold:
                    return instance
            return candidates[-1]


class LeastConnectionLoadBalancer(LoadBalancerSelector):
    """Selects the instance with the fewest active connections.

    Tracks active connections per instance and selects the one
    with the lowest count. Respects ``max_connections_per_instance``.
    Thread-safe.

    Args:
        max_connections_per_instance: Maximum connections per instance
            before it is excluded from selection.
    """

    def __init__(self, max_connections_per_instance: int = 1000) -> None:
        self._max = max_connections_per_instance
        self._lock = threading.RLock()
        self._connections: Dict[str, int] = {}

    async def select(
        self,
        instances: List[ServiceInstance],
        context: Optional[ResolveContext] = None,
    ) -> Optional[ServiceInstance]:
        if not instances:
            return None
        await asyncio.sleep(0)
        with self._lock:
            best_instance: Optional[ServiceInstance] = None
            best_count: int = -1
            for instance in instances:
                count = self._connections.get(instance.instance_id, 0)
                if count >= self._max:
                    continue
                if best_instance is None or count < best_count:
                    best_instance = instance
                    best_count = count
            return best_instance

    def acquire(self, instance_id: str) -> None:
        """Mark a connection as acquired for an instance.

        Args:
            instance_id: The instance identifier.
        """
        with self._lock:
            self._connections[instance_id] = (
                self._connections.get(instance_id, 0) + 1
            )

    def release(self, instance_id: str) -> None:
        """Release a connection for an instance.

        Args:
            instance_id: The instance identifier.
        """
        with self._lock:
            current = self._connections.get(instance_id, 0)
            if current > 0:
                self._connections[instance_id] = current - 1

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "selector": type(self).__name__,
                "max_connections_per_instance": self._max,
                "active_connections": dict(self._connections),
                "total_connections": sum(self._connections.values()),
            }


class LeastLatencyLoadBalancer(LoadBalancerSelector):
    """Selects the instance with the lowest EWMA latency.

    Uses an Exponentially Weighted Moving Average (EWMA) for
    latency tracking. Instances with zero recorded latency are
    preferred (assumed cold-start). Tracks p99, average, and
    timeout rates. Thread-safe.

    Args:
        window_size: Number of recent latency samples to retain.
    """

    def __init__(self, window_size: int = 10) -> None:
        self._window_size = window_size
        self._lock = threading.RLock()
        self._latencies: Dict[str, List[float]] = {}
        self._ewma: Dict[str, float] = {}
        self._timeouts: Dict[str, int] = {}
        self._requests: Dict[str, int] = {}
        self._alpha = 2.0 / (window_size + 1)

    async def select(
        self,
        instances: List[ServiceInstance],
        context: Optional[ResolveContext] = None,
    ) -> Optional[ServiceInstance]:
        if not instances:
            return None
        await asyncio.sleep(0)
        with self._lock:
            best_instance: Optional[ServiceInstance] = None
            best_latency: float = float("inf")
            for instance in instances:
                iid = instance.instance_id
                latency = self._ewma.get(iid)
                if latency is None:
                    return instance
                if latency < best_latency:
                    best_latency = latency
                    best_instance = instance
            return best_instance

    def record_latency(self, instance_id: str, latency: float) -> None:
        """Record a latency sample for an instance.

        Args:
            instance_id: The instance identifier.
            latency: Observed latency in milliseconds.
        """
        with self._lock:
            self._requests[instance_id] = (
                self._requests.get(instance_id, 0) + 1
            )
            if latency <= 0:
                self._timeouts[instance_id] = (
                    self._timeouts.get(instance_id, 0) + 1
                )
                return
            samples = self._latencies.setdefault(instance_id, [])
            samples.append(latency)
            if len(samples) > self._window_size:
                del samples[: len(samples) - self._window_size]
            prev_ewma = self._ewma.get(instance_id, latency)
            self._ewma[instance_id] = (self._alpha * latency) + (
                (1.0 - self._alpha) * prev_ewma
            )

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            p99_values: Dict[str, float] = {}
            avg_values: Dict[str, float] = {}
            timeout_rates: Dict[str, float] = {}
            for iid, samples in self._latencies.items():
                if samples:
                    sorted_samples = sorted(samples)
                    idx = max(0, int(len(sorted_samples) * 0.99) - 1)
                    p99_values[iid] = sorted_samples[idx]
                    avg_values[iid] = sum(samples) / len(samples)
                total = self._requests.get(iid, 0)
                timeouts = self._timeouts.get(iid, 0)
                timeout_rates[iid] = (timeouts / total) if total > 0 else 0.0
            return {
                "selector": type(self).__name__,
                "ewma": dict(self._ewma),
                "p99": p99_values,
                "avg": avg_values,
                "timeout_rates": timeout_rates,
                "requests": dict(self._requests),
                "timeouts": dict(self._timeouts),
            }


class RandomLoadBalancer(LoadBalancerSelector):
    """Selects an instance uniformly at random."""

    def __init__(self, seed: Optional[int] = None) -> None:
        self._seed = seed
        self._rng = random.Random(seed)
        self._lock = threading.RLock()
        self._select_count = 0

    async def select(
        self,
        instances: List[ServiceInstance],
        context: Optional[ResolveContext] = None,
    ) -> Optional[ServiceInstance]:
        if not instances:
            return None
        await asyncio.sleep(0)
        with self._lock:
            self._select_count += 1
            return self._rng.choice(instances)

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "selector": type(self).__name__,
                "seed": self._seed,
                "select_count": self._select_count,
            }


class ConsistentHashLoadBalancer(LoadBalancerSelector):
    """Selects an instance using a consistent hash ring.

    Uses MD5 hashing with virtual nodes to provide session
    affinity: the same hash key always maps to the same instance.
    Thread-safe.

    Args:
        hash_key_field: The context field used as the hash key
            (e.g. ``user_id``).
        vnodes: Number of virtual nodes per instance.
    """

    def __init__(self, hash_key_field: str = "user_id", vnodes: int = 100) -> None:
        self._hash_key_field = hash_key_field
        self._vnodes = vnodes
        self._lock = threading.RLock()
        self._ring: Dict[int, ServiceInstance] = {}
        self._sorted_keys: List[int] = []
        self._instances: Dict[str, ServiceInstance] = {}

    def _build_ring(self, instances: List[ServiceInstance]) -> None:
        self._ring.clear()
        self._sorted_keys.clear()
        self._instances.clear()
        for instance in instances:
            self._instances[instance.instance_id] = instance
            for i in range(self._vnodes):
                key = self._hash(f"{instance.instance_id}#{i}")
                self._ring[key] = instance
                self._sorted_keys.append(key)
        self._sorted_keys.sort()

    @staticmethod
    def _hash(key: str) -> int:
        import hashlib

        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def _get_hash_key(self, context: Optional[ResolveContext]) -> str:
        if context is None:
            return ""
        value = getattr(context, self._hash_key_field, None)
        if value is None:
            return ""
        return str(value)

    async def select(
        self,
        instances: List[ServiceInstance],
        context: Optional[ResolveContext] = None,
    ) -> Optional[ServiceInstance]:
        if not instances:
            return None
        await asyncio.sleep(0)
        with self._lock:
            if not self._ring or len(self._instances) != len(instances):
                self._build_ring(instances)
            if not self._sorted_keys:
                return instances[0]
            hash_key_str = self._get_hash_key(context)
            if not hash_key_str:
                return instances[0]
            hash_val = self._hash(hash_key_str)
            if hash_val <= self._sorted_keys[0]:
                return self._ring[self._sorted_keys[0]]
            if hash_val > self._sorted_keys[-1]:
                return self._ring[self._sorted_keys[0]]
            lo, hi = 0, len(self._sorted_keys) - 1
            while lo < hi:
                mid = (lo + hi) // 2
                if self._sorted_keys[mid] < hash_val:
                    lo = mid + 1
                else:
                    hi = mid
            return self._ring[self._sorted_keys[lo]]

    def get_stats(self) -> Dict[str, Any]:
        with self._lock:
            return {
                "selector": type(self).__name__,
                "hash_key_field": self._hash_key_field,
                "vnodes": self._vnodes,
                "ring_size": len(self._ring),
                "active_instances": len(self._instances),
            }