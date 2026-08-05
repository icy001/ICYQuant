"""TTL-based caching for service discovery resolution.

Provides ``ResolverCache`` which caches resolved service
instances with configurable TTL and hit/miss tracking.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

from ..instance import ServiceInstance

logger = logging.getLogger(__name__)


class ResolverCache:
    """TTL-based cache for resolved service instances.

    Stores resolved instance lists keyed by service name
    and context key, with automatic expiration based on
    a configurable time-to-live.

    Usage::

        cache = ResolverCache(ttl=5.0)
        cache.set("payment", "region=us-east", instances)
        cached = cache.get("payment", "region=us-east")
    """

    def __init__(self, ttl: float = 5.0) -> None:
        self._lock = threading.RLock()
        self._ttl = float(ttl)
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._hits = 0
        self._misses = 0
        self._sets = 0
        self._invalidations = 0

    def get(
        self,
        service_name: str,
        context_key: str,
    ) -> Optional[List[ServiceInstance]]:
        """Retrieve cached instances for a service and context.

        Args:
            service_name: The logical service name.
            context_key: A unique key representing the resolution
                context.

        Returns:
            Cached list of instances or None if not found
            or expired.
        """
        cache_key = f"{service_name}:{context_key}"
        with self._lock:
            entry = self._cache.get(cache_key)
            if entry is None:
                self._misses += 1
                return None

            expires_at = entry["expires_at"]
            if time.time() > expires_at:
                del self._cache[cache_key]
                self._misses += 1
                return None

            self._hits += 1
            instances = entry["instances"]
            if isinstance(instances, list):
                return list(instances)
            return None

    def set(
        self,
        service_name: str,
        context_key: str,
        instances: List[ServiceInstance],
    ) -> None:
        """Store resolved instances in the cache.

        Args:
            service_name: The logical service name.
            context_key: A unique key representing the resolution
                context.
            instances: The resolved instances to cache.
        """
        cache_key = f"{service_name}:{context_key}"
        with self._lock:
            self._cache[cache_key] = {
                "instances": list(instances),
                "expires_at": time.time() + self._ttl,
                "created_at": time.time(),
            }
            self._sets += 1

    def invalidate(self, service_name: str = None) -> None:
        """Invalidate cache entries.

        Args:
            service_name: If provided, only invalidate entries
                for this service. If None, invalidate all.
        """
        with self._lock:
            if service_name is None:
                count = len(self._cache)
                self._cache.clear()
                self._invalidations += count
                logger.debug("Cache invalidated completely (%d entries).", count)
            else:
                prefix = f"{service_name}:"
                keys_to_remove = [
                    k for k in self._cache if k.startswith(prefix)
                ]
                for key in keys_to_remove:
                    del self._cache[key]
                self._invalidations += len(keys_to_remove)
                logger.debug(
                    "Cache invalidated for '%s' (%d entries).",
                    service_name,
                    len(keys_to_remove),
                )

    def get_stats(self) -> Dict[str, Any]:
        """Return cache statistics.

        Returns:
            A dictionary with hit/miss/seth counts and cache
            size information.
        """
        with self._lock:
            total_requests = self._hits + self._misses
            return {
                "cache": "ResolverCache",
                "ttl": self._ttl,
                "hits": self._hits,
                "misses": self._misses,
                "sets": self._sets,
                "invalidations": self._invalidations,
                "size": len(self._cache),
                "hit_rate": (
                    self._hits / total_requests
                    if total_requests
                    else 0.0
                ),
            }

    def __repr__(self) -> str:
        with self._lock:
            return (
                f"ResolverCache(size={len(self._cache)}, "
                f"ttl={self._ttl}s, hits={self._hits})"
            )