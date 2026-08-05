"""Loader cache for the plugin loader subsystem.

Provides a thread-safe cache with TTL-based expiration for plugin
manifests, imported modules, and dependency trees. The cache is
organized into three namespaces:

- ``manifests``        : per-plugin :class:`PluginManifest` objects
- ``modules``          : imported module objects keyed by module path
- ``dependency_trees`` : dependency resolution trees keyed by plugin id

Entries expire after ``ttl_seconds`` (default 3600) and are lazily
purged during access and eviction.
"""

from __future__ import annotations

import logging
import threading
import time
import types as builtin_types
from typing import Any, Dict, Optional

from ..manifest import PluginManifest

logger = logging.getLogger(__name__)

DEFAULT_TTL = 3600.0


class LoaderCache:
    """Thread-safe cache for plugin loader artifacts.

    Maintains separate namespaces for manifests, modules, and
    dependency trees. All public methods are guarded by a
    reentrant lock for thread safety.

    Entries are cached with a creation timestamp and evicted when
    their age exceeds the configured TTL.
    """

    def __init__(self, ttl_seconds: float = DEFAULT_TTL) -> None:
        self._manifest_cache: Dict[str, tuple[PluginManifest, float]] = {}
        self._module_cache: Dict[str, tuple[builtin_types.ModuleType, float]] = {}
        self._dependency_tree_cache: Dict[str, tuple[Dict[str, Any], float]] = {}
        self._ttl_seconds = ttl_seconds
        self._lock = threading.RLock()
        self._stats: Dict[str, int] = {
            "manifest_hits": 0,
            "manifest_misses": 0,
            "module_hits": 0,
            "module_misses": 0,
            "tree_hits": 0,
            "tree_misses": 0,
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
            self._manifest_cache,
            self._module_cache,
            self._dependency_tree_cache,
        ):
            expired_keys = [
                k
                for k, (_, ts) in cache_dict.items()
                if (now - ts) > self._ttl_seconds
            ]
            for k in expired_keys:
                del cache_dict[k]
                self._stats["evictions"] += 1

    def get_manifest(self, plugin_id: str) -> Optional[PluginManifest]:
        """Retrieve a cached manifest for a plugin.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            The cached :class:`PluginManifest`, or ``None`` on miss
            or expiry.
        """
        with self._lock:
            self._evict_expired()
            entry = self._manifest_cache.get(plugin_id)
            if entry is None:
                self._stats["manifest_misses"] += 1
                return None
            self._stats["manifest_hits"] += 1
            return entry[0]

    def set_manifest(
        self, plugin_id: str, manifest: PluginManifest
    ) -> None:
        """Cache a manifest for a plugin.

        Args:
            plugin_id: The plugin identifier.
            manifest: The :class:`PluginManifest` to cache.
        """
        with self._lock:
            self._manifest_cache[plugin_id] = (manifest, time.time())
            logger.debug("Cached manifest for plugin '%s'.", plugin_id)

    def get_module(
        self, module_path: str
    ) -> Optional[builtin_types.ModuleType]:
        """Retrieve a cached imported module.

        Args:
            module_path: The dotted module path.

        Returns:
            The cached module, or ``None`` on miss or expiry.
        """
        with self._lock:
            self._evict_expired()
            entry = self._module_cache.get(module_path)
            if entry is None:
                self._stats["module_misses"] += 1
                return None
            self._stats["module_hits"] += 1
            return entry[0]

    def set_module(
        self, module_path: str, module: builtin_types.ModuleType
    ) -> None:
        """Cache an imported module.

        Args:
            module_path: The dotted module path.
            module: The imported module object.
        """
        with self._lock:
            self._module_cache[module_path] = (module, time.time())
            logger.debug("Cached module '%s'.", module_path)

    def get_dependency_tree(
        self, plugin_id: str
    ) -> Optional[Dict[str, Any]]:
        """Retrieve a cached dependency tree for a plugin.

        Args:
            plugin_id: The plugin identifier.

        Returns:
            The cached dependency tree dictionary, or ``None`` on miss
            or expiry.
        """
        with self._lock:
            self._evict_expired()
            entry = self._dependency_tree_cache.get(plugin_id)
            if entry is None:
                self._stats["tree_misses"] += 1
                return None
            self._stats["tree_hits"] += 1
            return dict(entry[0])

    def set_dependency_tree(
        self, plugin_id: str, tree: Dict[str, Any]
    ) -> None:
        """Cache a dependency tree for a plugin.

        Args:
            plugin_id: The plugin identifier.
            tree: The dependency tree dictionary to cache.
        """
        with self._lock:
            self._dependency_tree_cache[plugin_id] = (
                dict(tree),
                time.time(),
            )
            logger.debug(
                "Cached dependency tree for plugin '%s'.", plugin_id
            )

    def invalidate_plugin(self, plugin_id: str) -> None:
        """Clear all cached entries for a plugin.

        Removes the manifest, module, and dependency tree entries
        associated with the given plugin id.

        Args:
            plugin_id: The plugin identifier to invalidate.
        """
        with self._lock:
            removed = False
            if plugin_id in self._manifest_cache:
                del self._manifest_cache[plugin_id]
                removed = True
            if plugin_id in self._module_cache:
                del self._module_cache[plugin_id]
                removed = True
            if plugin_id in self._dependency_tree_cache:
                del self._dependency_tree_cache[plugin_id]
                removed = True
            if removed:
                self._stats["invalidations"] += 1
                logger.debug(
                    "Invalidated cache for plugin '%s'.", plugin_id
                )

    def invalidate_all(self) -> None:
        """Clear all cached entries across all namespaces."""
        with self._lock:
            self._manifest_cache.clear()
            self._module_cache.clear()
            self._dependency_tree_cache.clear()
            self._stats["invalidations"] += 1
            logger.debug("Invalidated all loader cache entries.")

    def clear(self) -> None:
        """Clear all cached entries and reset statistics."""
        with self._lock:
            self._manifest_cache.clear()
            self._module_cache.clear()
            self._dependency_tree_cache.clear()
            for key in self._stats:
                self._stats[key] = 0
            logger.debug("Loader cache cleared.")

    def get_stats(self) -> Dict[str, Any]:
        """Return cache statistics and namespace sizes."""
        with self._lock:
            manifest_hits = self._stats["manifest_hits"]
            manifest_misses = self._stats["manifest_misses"]
            module_hits = self._stats["module_hits"]
            module_misses = self._stats["module_misses"]
            tree_hits = self._stats["tree_hits"]
            tree_misses = self._stats["tree_misses"]

            total_hits = manifest_hits + module_hits + tree_hits
            total_misses = manifest_misses + module_misses + tree_misses
            total_lookups = total_hits + total_misses

            return {
                "ttl_seconds": self._ttl_seconds,
                "manifest_entries": len(self._manifest_cache),
                "module_entries": len(self._module_cache),
                "dependency_tree_entries": len(
                    self._dependency_tree_cache
                ),
                "manifest_hits": manifest_hits,
                "manifest_misses": manifest_misses,
                "module_hits": module_hits,
                "module_misses": module_misses,
                "tree_hits": tree_hits,
                "tree_misses": tree_misses,
                "evictions": self._stats["evictions"],
                "invalidations": self._stats["invalidations"],
                "hit_rate": (
                    total_hits / total_lookups
                    if total_lookups > 0
                    else 0.0
                ),
            }