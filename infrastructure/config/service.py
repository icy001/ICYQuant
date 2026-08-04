"""
Configuration platform service.

Unified service layer that integrates all configuration
platform components into a single service interface.

Manages:
- Configuration Manager
- Environment Manager
- Registry
- Dynamic Configuration Manager
- Snapshot Manager
- Watcher
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from .bootstrap import ConfigurationBootstrap
from .container import DIContainer
from .lifecycle import ConfigurationLifecycle, LifecycleState

logger = logging.getLogger(__name__)


class ConfigurationService:
    """
    Unified configuration platform service.

    Provides a single entry point for all configuration
    operations, integrating static configuration,
    environment management, and dynamic configuration.

    Usage:
        service = ConfigurationService()
        await service.startup()

        # Get configuration value
        port = service.get("server.port")

        # Reload configuration
        await service.reload()

        # Switch environment
        service.switch_environment("production")

        # Shutdown
        await service.shutdown()
    """

    def __init__(
        self,
        container: Optional[DIContainer] = None,
        config_files: Optional[List[str]] = None,
        watch_files: Optional[List[str]] = None,
        enable_watcher: bool = True,
        enable_scheduler: bool = False,
    ) -> None:
        """
        Initialize configuration service.

        Args:
            container: DI container.
            config_files: Configuration files to load.
            watch_files: Files to watch.
            enable_watcher: Enable watcher.
            enable_scheduler: Enable scheduler.
        """
        self._bootstrap = ConfigurationBootstrap(
            container=container,
            config_files=config_files,
            watch_files=watch_files,
            enable_watcher=enable_watcher,
            enable_scheduler=enable_scheduler,
        )
        self._container = self._bootstrap.container
        self._lifecycle = self._bootstrap.lifecycle
        self._started = False

        # Component references (populated on startup)
        self._config_manager = None
        self._env_manager = None
        self._registry = None
        self._dynamic_mgr = None

    @property
    def lifecycle(
        self,
    ) -> ConfigurationLifecycle:
        """Get lifecycle manager."""
        return self._lifecycle

    @property
    def container(
        self,
    ) -> DIContainer:
        """Get DI container."""
        return self._container

    @property
    def bootstrap(
        self,
    ) -> ConfigurationBootstrap:
        """Get bootstrap."""
        return self._bootstrap

    @property
    def is_started(
        self,
    ) -> bool:
        """Check if service is started."""
        return self._started

    # ── Lifecycle ──

    async def startup(
        self,
    ) -> Dict[str, Any]:
        """
        Start the configuration service.

        Returns:
            Startup result.
        """
        result = await self._bootstrap.startup()

        if result.get("success"):
            self._started = True
            self._resolve_components()

        return result

    async def reload(
        self,
        operator: str = "system",
        reason: str = "service reload",
    ) -> Dict[str, Any]:
        """
        Reload configuration.

        Args:
            operator: Who triggered the reload.
            reason: Reason for reload.

        Returns:
            Reload result.
        """
        if not self._started:
            return {"success": False, "error": "Service not started"}

        # Reload via dynamic manager if available
        if self._dynamic_mgr:
            result = self._dynamic_mgr.reload(
                operator=operator,
                reason=reason,
            )
            return result.to_dict()

        # Fallback to lifecycle reload
        return await self._lifecycle.reload()

    async def shutdown(
        self,
        timeout: float = 30.0,
    ) -> Dict[str, Any]:
        """
        Shut down the configuration service.

        Args:
            timeout: Shutdown timeout.

        Returns:
            Shutdown result.
        """
        result = await self._bootstrap.shutdown(timeout=timeout)
        self._started = False
        self._config_manager = None
        self._env_manager = None
        self._registry = None
        self._dynamic_mgr = None
        return result

    # ── Configuration Access ──

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Get a configuration value.

        Args:
            key: Configuration key.
            default: Default value.

        Returns:
            Configuration value.
        """
        # Try dynamic manager first
        if self._dynamic_mgr and self._dynamic_mgr.current_snapshot:
            return self._dynamic_mgr.current_snapshot.get(key, default)

        # Fallback to config manager
        if self._config_manager:
            return self._config_manager.get(key, default)

        return default

    def get_typed(
        self,
        key: str,
        value_type: type,
        default: Any = None,
    ) -> Any:
        """Get a typed configuration value."""
        if self._config_manager:
            return self._config_manager.get_typed(key, value_type, default)
        return default

    def get_all(
        self,
    ) -> Dict[str, Any]:
        """Get all configuration values."""
        if self._dynamic_mgr and self._dynamic_mgr.current_snapshot:
            return dict(self._dynamic_mgr.current_snapshot.values)
        if self._config_manager:
            snapshot = self._config_manager.get_snapshot()
            return dict(snapshot.values) if hasattr(snapshot, "values") else {}
        return {}

    def set(
        self,
        key: str,
        value: Any,
    ) -> None:
        """Set a configuration value."""
        if self._config_manager:
            self._config_manager.set(key, value)

    def exists(
        self,
        key: str,
    ) -> bool:
        """Check if a key exists."""
        if self._dynamic_mgr and self._dynamic_mgr.current_snapshot:
            return self._dynamic_mgr.current_snapshot.contains(key)
        if self._config_manager:
            return self._config_manager.exists(key)
        return False

    # ── Environment Management ──

    def switch_environment(
        self,
        profile_name: str,
    ) -> Any:
        """
        Switch to a different environment profile.

        Args:
            profile_name: Profile to switch to.

        Returns:
            Activated profile.
        """
        if self._env_manager:
            return self._env_manager.switch(profile_name)
        return None

    @property
    def current_environment(
        self,
    ) -> Optional[str]:
        """Get current environment name."""
        if self._env_manager:
            return self._env_manager.active_profile_name
        return None

    def list_environments(
        self,
    ) -> List[str]:
        """List available environments."""
        if self._env_manager:
            return self._env_manager.list_profiles()
        return []

    # ── Dynamic Configuration ──

    async def rollback(
        self,
        version: int,
        operator: str = "admin",
    ) -> Dict[str, Any]:
        """
        Rollback to a specific version.

        Args:
            version: Target version.
            operator: Who triggered the rollback.

        Returns:
            Rollback result.
        """
        if self._dynamic_mgr:
            result = self._dynamic_mgr.rollback_to(version, operator=operator)
            if result:
                return result.to_dict()
        return {"success": False, "error": "Dynamic manager not available"}

    def subscribe(
        self,
        callback: Any,
        prefixes: Optional[set] = None,
    ) -> str:
        """
        Subscribe to configuration changes.

        Args:
            callback: Callback function.
            prefixes: Key prefixes to watch.

        Returns:
            Subscription ID.
        """
        if self._dynamic_mgr:
            return self._dynamic_mgr.subscribe(
                callback=callback,
                subscribed_prefixes=prefixes,
            )
        return ""

    def unsubscribe(
        self,
        subscription_id: str,
    ) -> bool:
        """Unsubscribe from configuration changes."""
        if self._dynamic_mgr:
            return self._dynamic_mgr.unsubscribe(subscription_id)
        return False

    # ── Status ──

    def get_status(
        self,
    ) -> Dict[str, Any]:
        """Get service status."""
        status = {
            "started": self._started,
            "lifecycle": self._lifecycle.get_status(),
        }

        if self._config_manager:
            status["config_manager"] = self._config_manager.get_stats()

        if self._env_manager:
            status["environment"] = self._env_manager.get_status()

        if self._dynamic_mgr:
            status["dynamic"] = self._dynamic_mgr.get_status()

        return status

    def _resolve_components(
        self,
    ) -> None:
        """Resolve component references from container."""
        from .manager import ConfigurationManager
        from .environment.manager import EnvironmentManager
        from .dynamic.manager import DynamicConfigurationManager
        from .registry import ConfigurationRegistry

        self._config_manager = self._container.resolve(ConfigurationManager)
        self._env_manager = self._container.resolve(EnvironmentManager)
        self._registry = self._container.resolve(ConfigurationRegistry)
        self._dynamic_mgr = self._container.resolve(DynamicConfigurationManager)
