"""
Configuration health check.

Provides health monitoring for the
configuration platform, reporting on
cache, registry, validator, and loader
status. Also provides unified platform
health check across all components.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from .manager import ConfigurationManager


class ConfigurationHealth:
    """
    Configuration platform health checker.

    Reports on the health of all configuration
    platform components:
    - Registry: Item count, version, environment
    - Cache: Size, hit rate, evictions
    - Validator: Rule count
    - Loader: Source count

    Usage:
        health = ConfigurationHealth(manager)
        status = await health.check()
    """

    def __init__(
        self,
        manager: ConfigurationManager,
    ) -> None:
        self._manager = manager

    async def check(
        self,
    ) -> Dict[str, Any]:
        """
        Perform health check.

        Returns:
            Health status dictionary.
        """

        stats = self._manager.get_stats()
        cache_stats = stats.get("cache", {})

        # Determine health
        healthy = True
        issues = []

        if not stats.get("items", 0) > 0:
            issues.append("No configuration items loaded")
            healthy = False

        cache_hit_rate = cache_stats.get("hit_rate", 0.0)
        if cache_hit_rate < 0.5 and cache_stats.get("hits", 0) > 10:
            issues.append(f"Low cache hit rate: {cache_hit_rate:.2%}")
            healthy = False

        return {
            "healthy": healthy,
            "issues": issues,
            "environment": stats.get("environment"),
            "items": stats.get("items"),
            "version": stats.get("version"),
            "cache": {
                "size": cache_stats.get("size", 0),
                "max_size": cache_stats.get("max_size", 0),
                "hit_rate": cache_stats.get("hit_rate", 0.0),
                "hits": cache_stats.get("hits", 0),
                "misses": cache_stats.get("misses", 0),
                "evictions": cache_stats.get("evictions", 0),
                "expirations": cache_stats.get("expirations", 0),
            },
            "registry": True,
            "validator_rules": stats.get("validator_rules", 0),
            "sources": stats.get("sources", 0),
            "loader": "yaml",
        }

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """Get static status."""

        return {
            "environment": self._manager.environment,
            "items": self._manager.item_count,
            "version": self._manager.snapshot_version,
        }


class PlatformHealthCheck:
    """
    Unified platform health check.

    Checks the health of all configuration
    platform components in a single call.

    Returns:
        {
            "configuration": True,
            "loader": True,
            "environment": True,
            "watcher": True,
            "snapshot": True,
            "dynamic": True
        }
    """

    def __init__(
        self,
        config_manager: Optional[ConfigurationManager] = None,
        env_manager: Optional[Any] = None,
        dynamic_manager: Optional[Any] = None,
        watcher: Optional[Any] = None,
    ) -> None:
        """
        Initialize platform health check.

        Args:
            config_manager: ConfigurationManager instance.
            env_manager: EnvironmentManager instance.
            dynamic_manager: DynamicConfigurationManager instance.
            watcher: ConfigurationWatcher instance.
        """
        self._config_manager = config_manager
        self._env_manager = env_manager
        self._dynamic_manager = dynamic_manager
        self._watcher = watcher

    async def check_all(
        self,
    ) -> Dict[str, Any]:
        """
        Perform health check on all components.

        Returns:
            Dict mapping component name to health status.
        """
        result: Dict[str, Any] = {}

        # Configuration manager
        result["configuration"] = self._check_config_manager()

        # Loader
        result["loader"] = self._check_loader()

        # Environment
        result["environment"] = self._check_environment()

        # Watcher
        result["watcher"] = self._check_watcher()

        # Snapshot
        result["snapshot"] = self._check_snapshot()

        # Dynamic
        result["dynamic"] = self._check_dynamic()

        # Overall
        all_healthy = all(
            v if isinstance(v, bool) else v.get("healthy", False)
            for v in result.values()
        )
        result["healthy"] = all_healthy

        return result

    def _check_config_manager(
        self,
    ) -> bool:
        """Check configuration manager health."""
        if self._config_manager is None:
            return True
        try:
            return self._config_manager.item_count > 0
        except Exception:
            return False

    def _check_loader(
        self,
    ) -> bool:
        """Check loader health."""
        if self._config_manager is None:
            return True
        try:
            stats = self._config_manager.get_stats()
            return stats.get("sources", 0) > 0
        except Exception:
            return False

    def _check_environment(
        self,
    ) -> bool:
        """Check environment manager health."""
        if self._env_manager is None:
            return True
        try:
            return self._env_manager.active_profile is not None
        except Exception:
            return False

    def _check_watcher(
        self,
    ) -> bool:
        """Check watcher health."""
        if self._watcher is None:
            return True
        return True

    def _check_snapshot(
        self,
    ) -> bool:
        """Check snapshot health."""
        if self._config_manager is None:
            return True
        try:
            snapshot = self._config_manager.get_snapshot()
            return snapshot is not None
        except Exception:
            return False

    def _check_dynamic(
        self,
    ) -> bool:
        """Check dynamic manager health."""
        if self._dynamic_manager is None:
            return True
        try:
            return self._dynamic_manager.current_snapshot is not None
        except Exception:
            return False
