"""Marketplace cache.

Provides :class:`MarketplaceCache` for thread-safe TTL-based caching
of package information, repository indices, and search results.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

DEFAULT_TTL = 1800.0


class MarketplaceCache:
    """Thread-safe TTL-based cache for marketplace artifacts.

    Maintains separate namespaces for package info, repository
    indices, and search results.  All public methods are guarded
    by a reentrant lock for thread safety.

    Entries are cached with a creation timestamp and evicted when
    their age exceeds the configured TTL (default 1800 seconds).

    Attributes:
        _ttl_seconds: Time-to-live for cache entries.
        _lock: Thread-safe reentrant lock.
    """

    def __init__(self, ttl_seconds: float = DEFAULT_TTL) -> None:
        self._package_cache: Dict[str, tuple[Dict[str, Any], float]] = {}
        self._repo_cache: Dict[str, tuple[List[Dict[str, Any]], float]] = {}
        self._search_cache: Dict[str, tuple[List[Dict[str, Any]], float]] = {}
        self._ttl_seconds = ttl_seconds
        self._lock = threading.RLock()
        self._stats: Dict[str, int] = {
            "package_hits": 0,
            "package_misses": 0,
            "repo_hits": 0,
            "repo_misses": 0,
            "search_hits": 0,
            "search_misses": 0,
            "evictions": 0,
            "invalidations": 0,
        }

    def _is_expired(self, timestamp: float) -> bool:
        """Check whether a timestamp exceeds the TTL."""
        return (time.time() - timestamp) > self._ttl_seconds

    def _evict_expired(self) -> None:
        """Lazily purge expired entries from all namespaces."""
        now = time.time()
        for cache_dict in (
            self._package_cache,
            self._repo_cache,
            self._search_cache,
        ):
            expired_keys = [
                k
                for k, (_, ts) in cache_dict.items()
                if (now - ts) > self._ttl_seconds
            ]
            for k in expired_keys:
                del cache_dict[k]
                self._stats["evictions"] += 1

    def _package_key(self, plugin_id: str, version: Optional[str]) -> str:
        """Build a cache key for a package entry."""
        if version:
            return f"{plugin_id}@{version}"
        return plugin_id

    def get_package_info(
        self, plugin_id: str, version: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Retrieve cached package information.

        Args:
            plugin_id: The plugin identifier.
            version: Optional version string.

        Returns:
            The cached package info dictionary, or ``None`` on miss
            or expiry.
        """
        with self._lock:
            self._evict_expired()
            key = self._package_key(plugin_id, version)
            entry = self._package_cache.get(key)
            if entry is None:
                self._stats["package_misses"] += 1
                return None
            self._stats["package_hits"] += 1
            return dict(entry[0])

    def set_package_info(
        self,
        plugin_id: str,
        version: str,
        info: Dict[str, Any],
    ) -> None:
        """Cache package information.

        Args:
            plugin_id: The plugin identifier.
            version: The package version string.
            info: The package info dictionary to cache.
        """
        with self._lock:
            key = self._package_key(plugin_id, version)
            self._package_cache[key] = (dict(info), time.time())
            logger.debug(
                "Cached package info for '%s' version '%s'.",
                plugin_id,
                version,
            )

    def get_repository_index(
        self, repo_name: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Retrieve a cached repository index.

        Args:
            repo_name: The repository name or URL.

        Returns:
            The cached index as a list of dictionaries, or ``None``
            on miss or expiry.
        """
        with self._lock:
            self._evict_expired()
            entry = self._repo_cache.get(repo_name)
            if entry is None:
                self._stats["repo_misses"] += 1
                return None
            self._stats["repo_hits"] += 1
            return list(entry[0])

    def set_repository_index(
        self, repo_name: str, index: List[Dict[str, Any]]
    ) -> None:
        """Cache a repository index.

        Args:
            repo_name: The repository name or URL.
            index: The repository index list to cache.
        """
        with self._lock:
            self._repo_cache[repo_name] = (list(index), time.time())
            logger.debug(
                "Cached repository index for '%s'.", repo_name
            )

    def get_search_results(
        self, query: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Retrieve cached search results.

        Args:
            query: The search query string.

        Returns:
            The cached search results list, or ``None`` on miss
            or expiry.
        """
        with self._lock:
            self._evict_expired()
            entry = self._search_cache.get(query)
            if entry is None:
                self._stats["search_misses"] += 1
                return None
            self._stats["search_hits"] += 1
            return list(entry[0])

    def set_search_results(
        self, query: str, results: List[Dict[str, Any]]
    ) -> None:
        """Cache search results.

        Args:
            query: The search query string.
            results: The search results list to cache.
        """
        with self._lock:
            self._search_cache[query] = (list(results), time.time())
            logger.debug(
                "Cached search results for query '%s'.", query
            )

    def invalidate_plugin(self, plugin_id: str) -> None:
        """Clear all cached entries for a plugin.

        Args:
            plugin_id: The plugin identifier to invalidate.
        """
        with self._lock:
            removed = False
            keys_to_remove = [
                k
                for k in self._package_cache
                if k == plugin_id or k.startswith(f"{plugin_id}@")
            ]
            for k in keys_to_remove:
                del self._package_cache[k]
                removed = True
            if removed:
                self._stats["invalidations"] += 1
                logger.debug(
                    "Invalidated cache for plugin '%s'.", plugin_id
                )

    def invalidate_repository(self, repo_name: str) -> None:
        """Clear cached entries for a repository.

        Args:
            repo_name: The repository name or URL to invalidate.
        """
        with self._lock:
            if repo_name in self._repo_cache:
                del self._repo_cache[repo_name]
                self._stats["invalidations"] += 1
                logger.debug(
                    "Invalidated cache for repository '%s'.",
                    repo_name,
                )

    def invalidate_all(self) -> None:
        """Clear all cached entries across all namespaces."""
        with self._lock:
            self._package_cache.clear()
            self._repo_cache.clear()
            self._search_cache.clear()
            self._stats["invalidations"] += 1
            logger.debug("Invalidated all marketplace cache entries.")

    def clear(self) -> None:
        """Clear all cached entries and reset statistics."""
        with self._lock:
            self._package_cache.clear()
            self._repo_cache.clear()
            self._search_cache.clear()
            for key in self._stats:
                self._stats[key] = 0
            logger.debug("Marketplace cache cleared.")

    def get_stats(self) -> Dict[str, Any]:
        """Return cache statistics and namespace sizes.

        Returns:
            A dictionary with TTL, entry counts, hit/miss counts,
            and hit rate.
        """
        with self._lock:
            package_hits = self._stats["package_hits"]
            package_misses = self._stats["package_misses"]
            repo_hits = self._stats["repo_hits"]
            repo_misses = self._stats["repo_misses"]
            search_hits = self._stats["search_hits"]
            search_misses = self._stats["search_misses"]

            total_hits = package_hits + repo_hits + search_hits
            total_misses = (
                package_misses + repo_misses + search_misses
            )
            total_lookups = total_hits + total_misses

            return {
                "ttl_seconds": self._ttl_seconds,
                "package_entries": len(self._package_cache),
                "repository_entries": len(self._repo_cache),
                "search_entries": len(self._search_cache),
                "package_hits": package_hits,
                "package_misses": package_misses,
                "repo_hits": repo_hits,
                "repo_misses": repo_misses,
                "search_hits": search_hits,
                "search_misses": search_misses,
                "evictions": self._stats["evictions"],
                "invalidations": self._stats["invalidations"],
                "hit_rate": (
                    total_hits / total_lookups
                    if total_lookups > 0
                    else 0.0
                ),
            }