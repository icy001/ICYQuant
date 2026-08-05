"""Consistent hash selection algorithm.

Provides a thread-safe ``ConsistentHash`` class that uses an MD5
hash ring with virtual nodes to ensure session affinity: the same
hash key always maps to the same instance.
"""

from __future__ import annotations

import hashlib
import logging
import threading
from typing import Any, Dict, List, Optional

from ..instance import ServiceInstance

logger = logging.getLogger(__name__)


class ConsistentHash:
    """Selects an instance using a consistent hash ring.

    Uses MD5 hashing with virtual nodes to provide session
    affinity. The same hash key always maps to the same instance
    (as long as that instance remains in the ring). Thread-safe.

    Args:
        hash_key_field: The metadata field name used as the hash
            key (e.g. ``user_id``).
        vnodes: Number of virtual nodes per instance for better
            distribution.

    Usage::

        ch = ConsistentHash(hash_key_field="user_id", vnodes=100)
        instance = ch.select(instances, key="user-123")
    """

    def __init__(
        self, hash_key_field: str = "user_id", vnodes: int = 100
    ) -> None:
        self._hash_key_field = hash_key_field
        self._vnodes = max(1, vnodes)
        self._lock = threading.RLock()
        self._ring: Dict[int, ServiceInstance] = {}
        self._sorted_keys: List[int] = []
        self._instances: Dict[str, ServiceInstance] = {}
        self._select_count = 0

    def _build_ring(self, instances: List[ServiceInstance]) -> None:
        """Rebuild the hash ring from the given instances.

        Args:
            instances: The instances to add to the ring.
        """
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
        """Compute an MD5 hash of a string key.

        Args:
            key: The string to hash.

        Returns:
            Integer hash value.
        """
        return int(hashlib.md5(key.encode()).hexdigest(), 16)

    def _resolve_key(
        self, instances: List[ServiceInstance], key: Optional[str]
    ) -> str:
        """Resolve the hash key from context or instances.

        Args:
            instances: Candidate instances (used as fallback).
            key: Explicit key to use.

        Returns:
            The resolved hash key string.
        """
        if key is not None:
            return str(key)
        if instances:
            first = instances[0]
            if isinstance(first.metadata, dict):
                value = first.metadata.get(self._hash_key_field)
                if value is not None:
                    return str(value)
        return ""

    def select(
        self,
        instances: List[ServiceInstance],
        key: Optional[str] = None,
    ) -> Optional[ServiceInstance]:
        """Select an instance using consistent hashing.

        Args:
            instances: Candidate instances.
            key: Optional explicit hash key. If not provided,
                the key is derived from the first instance's
                metadata using ``hash_key_field``.

        Returns:
            The selected instance or None if the list is empty.
        """
        if not instances:
            return None
        with self._lock:
            if not self._ring or len(self._instances) != len(instances):
                self._build_ring(instances)
            if not self._sorted_keys:
                return instances[0]
            resolved_key = self._resolve_key(instances, key)
            if not resolved_key:
                return instances[0]
            hash_val = self._hash(resolved_key)
            self._select_count += 1
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
        """Return consistent hash statistics.

        Returns:
            A dictionary with ring size, vnodes, and select count.
        """
        with self._lock:
            return {
                "selector": "ConsistentHash",
                "hash_key_field": self._hash_key_field,
                "vnodes": self._vnodes,
                "ring_size": len(self._ring),
                "active_instances": len(self._instances),
                "select_count": self._select_count,
            }

    def __repr__(self) -> str:
        return (
            f"ConsistentHash(key_field={self._hash_key_field!r}, "
            f"vnodes={self._vnodes}, ring_size={len(self._ring)})"
        )