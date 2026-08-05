"""Service repository with TTL-based caching.

Provides ``ServiceRepository`` for caching service and instance
lookups with time-to-live expiry, reducing load on the backend
registry. All operations are thread-safe.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

from .instance import ServiceInstance
from .service import Service

logger = logging.getLogger(__name__)


class ServiceRepository:
    """A TTL-based cache for service and instance lookups.

    Args:
        ttl: Time-to-live in seconds for cached entries. Defaults to 30.
        max_entries: Maximum number of cached service entries.
    """

    def __init__(self, ttl: float = 30.0, max_entries: int = 10000) -> None:
        self._ttl = float(ttl) if ttl and ttl > 0 else 30.0
        self._max_entries = int(max_entries) if max_entries > 0 else 10000
        self._lock = threading.RLock()
        self._cache: Dict[str, Tuple[Service, float]] = {}
        self._hits = 0
        self._misses = 0
        self._evictions = 0

    def _make_key(self, service_name: str, namespace: str = "default") -> str:
        return f"{namespace}:{service_name}"

    def _is_expired(self, timestamp: float) -> bool:
        return (time.time() - timestamp) > self._ttl

    def get_service(
        self, service_name: str, namespace: str = "default"
    ) -> Optional[Service]:
        """Return a cached service if present and not expired.

        Args:
            service_name: The logical service name.
            namespace: The namespace to look up.

        Returns:
            The cached ``Service`` or None on miss/expiry.
        """
        key = self._make_key(service_name, namespace)
        with self._lock:
            entry = self._cache.get(key)
            if entry is None:
                self._misses += 1
                return None
            service, timestamp = entry
            if self._is_expired(timestamp):
                self._cache.pop(key, None)
                self._misses += 1
                return None
            self._hits += 1
            return service

    def set_service(self, service: Service) -> None:
        """Store or refresh a service in the cache.

        Args:
            service: The ``Service`` to cache.
        """
        if service is None:
            return
        key = self._make_key(service.name, service.namespace)
        with self._lock:
            if len(self._cache) >= self._max_entries and key not in self._cache:
                self._evict_oldest()
            self._cache[key] = (service, time.time())

    def remove_service(self, service_name: str, namespace: str = "default") -> None:
        """Remove a service from the cache.

        Args:
            service_name: The logical service name.
            namespace: The namespace to remove from.
        """
        key = self._make_key(service_name, namespace)
        with self._lock:
            self._cache.pop(key, None)

    def get_instances(
        self, service_name: str, namespace: str = "default"
    ) -> List[ServiceInstance]:
        """Return cached instances for a service.

        Args:
            service_name: The logical service name.
            namespace: The namespace to look up.

        Returns:
            A list of ``ServiceInstance`` objects. Empty on miss.
        """
        service = self.get_service(service_name, namespace)
        if service is None:
            return []
        return service.get_instances(healthy_only=False)

    def get_all_services(self, namespace: str = "default") -> List[Service]:
        """Return all non-expired cached services for a namespace.

        Args:
            namespace: The namespace to list.

        Returns:
            A list of ``Service`` objects.
        """
        results: List[Service] = []
        with self._lock:
            expired_keys: List[str] = []
            for key, (service, timestamp) in self._cache.items():
                if self._is_expired(timestamp):
                    expired_keys.append(key)
                    continue
                if service.namespace == namespace:
                    results.append(service)
            for key in expired_keys:
                self._cache.pop(key, None)
        return results

    def invalidate(self, service_name: str = None) -> None:
        """Invalidate cached entries.

        Args:
            service_name: When provided, invalidate only entries with
                this service name across all namespaces. When None,
                no-op (use ``invalidate_all`` to clear everything).
        """
        if service_name is None:
            return
        with self._lock:
            keys_to_remove = [
                key for key in self._cache
                if key.endswith(f":{service_name}")
            ]
            for key in keys_to_remove:
                self._cache.pop(key, None)
            logger.debug(
                "Invalidated %d cache entries for service '%s'.",
                len(keys_to_remove),
                service_name,
            )

    def invalidate_all(self) -> None:
        """Clear all cached entries."""
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            logger.debug("Invalidated all %d cache entries.", count)

    def _evict_oldest(self) -> None:
        """Evict the entry with the oldest timestamp."""
        if not self._cache:
            return
        oldest_key = min(self._cache, key=lambda k: self._cache[k][1])
        self._cache.pop(oldest_key, None)
        self._evictions += 1

    def cleanup_expired(self) -> int:
        """Remove all expired entries from the cache.

        Returns:
            The number of entries removed.
        """
        removed = 0
        with self._lock:
            expired_keys = [
                key for key, (_, ts) in self._cache.items()
                if self._is_expired(ts)
            ]
            for key in expired_keys:
                self._cache.pop(key, None)
                removed += 1
        if removed:
            logger.debug("Cleaned up %d expired cache entries.", removed)
        return removed

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics for the repository.

        Returns:
            A dictionary with cache size, hit/miss counts, and TTL.
        """
        with self._lock:
            total = self._hits + self._misses
            return {
                "ttl_seconds": self._ttl,
                "max_entries": self._max_entries,
                "current_entries": len(self._cache),
                "hits": self._hits,
                "misses": self._misses,
                "evictions": self._evictions,
                "hit_rate": (self._hits / total) if total else 0.0,
            }

    def __repr__(self) -> str:
        return (
            f"ServiceRepository(entries={len(self._cache)}, "
            f"ttl={self._ttl}s)"
        )
